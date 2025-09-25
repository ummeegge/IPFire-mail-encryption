#!/usr/bin/perl
###############################################################################
#                                                                             #
# IPFire.org - A linux based firewall                                         #
# Copyright (C) 2007-2020  IPFire Team  <info@ipfire.org>                     #
#                                                                             #
# This program is free software: you can redistribute it and/or modify        #
# it under the terms of the GNU General Public License as published by        #
# the Free Software Foundation, either version 3 of the License, or           #
# (at your option) any later version.                                         #
#                                                                             #
# This program is distributed in the hope that it will be useful,             #
# but WITHOUT ANY WARRANTY; without even the implied warranty of              #
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the               #
# GNU General Public License for more details.                                #
#                                                                             #
# You should have received a copy of the GNU General Public License           #
# along with this program.  If not, see <http://www.gnu.org/licenses/>.       #
#                                                                             #
###############################################################################

use strict;

#enable only the following on debugging purpose
#use warnings;
#use CGI::Carp 'fatalsToBrowser';

use MIME::Lite;
use CGI qw(param);
use File::Temp qw(tempfile);
use Time::Local;
use POSIX qw(strftime);

require '/var/ipfire/general-functions.pl';
require "${General::swroot}/lang.pl";
require "${General::swroot}/header.pl";

my $dmafile = "${General::swroot}/dma/dma.conf";
my $authfile = "${General::swroot}/dma/auth.conf";
my $mailfile = "${General::swroot}/dma/mail.conf";
my $gpgdir = "${General::swroot}/dma/encryption";
my %dma = ();
my %auth = ();
my %mail = ();
my %mainsettings = ();
my %cgiparams = ();
my %color = ();
my %checked = ();
my %selected = ();
my $errormessage = '';
my $infomessage = '';

# Initialize HTTP headers
&Header::showhttpheaders();
&General::readhash("${General::swroot}/main/settings", \%mainsettings);
&General::readhash("/srv/web/ipfire/html/themes/ipfire/include/colors.txt", \%color);
&Header::getcgihash(\%cgiparams);

# Read dma.conf configuration
if (-f $dmafile) {
    open(FILE, "<", $dmafile) or die "Cannot open $dmafile: $!";
    foreach my $line (<FILE>) {
        $line =~ m/^([A-Z]+)\s+(.*)$/;
        $dma{$1} = $2 if $1;
    }
    close FILE;
} else {
    open(FILE, ">$dmafile") or die "Cannot create $dmafile: $!";
    close FILE;
}

# Read auth.conf configuration
if (-f $authfile) {
    open(FILE, "<", $authfile) or die "Cannot open $authfile: $!";
    my $authline = <FILE>;
    if ($authline) {
        my @part1 = split(/\|/, $authline);
        my @part2 = split(/\:/, $part1[1]);
        $auth{'AUTHNAME'} = $part1[0];
        $auth{'AUTHHOST'} = $part2[0];
        $auth{'AUTHPASS'} = $part2[1];
    }
    close FILE;
}

# Read mail.conf configuration
if (-f $mailfile) {
    &General::readhash($mailfile, \%mail);
}

# Check if GPG directory exists
if (! -d $gpgdir) {
    $errormessage = "GPG key management: $gpgdir does not exist. Run install.sh.";
}

# Handle form actions
my $action = $cgiparams{'ACTION'} // '';
if ($action eq "Save") {
    $errormessage = &checkmailsettings();
    if (!$errormessage) {
        %dma = ();
        %auth = ();
        %mail = ();
        open(TXT, ">$dmafile") or die "Cannot open $dmafile: $!";
        open(TXT1, ">$authfile") or die "Cannot open $authfile: $!";
        open(TXT2, ">$mailfile") or die "Cannot open $mailfile: $!";
        close TXT2;

        # Store mail settings
        $mail{'USEMAIL'} = $cgiparams{'USEMAIL'} // 'off';
        $mail{'SENDER'} = $cgiparams{'txt_mailsender'} // '';
        $mail{'RECIPIENT'} = $cgiparams{'txt_recipient'} // '';
        $mail{'MASQUERADE'} = $cgiparams{'txt_masquerade'} // '';
        $mail{'ENCRYPT'} = $cgiparams{'ENCRYPT'} // 'off';
        $mail{'GPG_KEY'} = $cgiparams{'GPG_KEY'} // '';

        # Store authentication settings
        if ($cgiparams{'txt_mailuser'} && $cgiparams{'txt_mailpass'}) {
            $auth{'AUTHNAME'} = $cgiparams{'txt_mailuser'};
            $auth{'AUTHPASS'} = $cgiparams{'txt_mailpass'};
            $auth{'AUTHHOST'} = $cgiparams{'txt_mailserver'};
            print TXT1 "$auth{'AUTHNAME'}|$auth{'AUTHHOST'}:$auth{'AUTHPASS'}\n";
        }

        # Store DMA settings
        $dma{'SMARTHOST'} = $cgiparams{'txt_mailserver'} // '';
        $dma{'PORT'} = $cgiparams{'txt_mailport'} // '';
        $dma{'STARTTLS'} = '' if ($cgiparams{'mail_tls'} // '' eq 'explicit');
        $dma{'SECURETRANSFER'} = '' if ($cgiparams{'mail_tls'} // '' eq 'explicit' || $cgiparams{'mail_tls'} // '' eq 'implicit');
        $dma{'SPOOLDIR'} = "/var/spool/dma";
        $dma{'FULLBOUNCE'} = '';
        $dma{'MAILNAME'} = "$mainsettings{'HOSTNAME'}.$mainsettings{DOMAINNAME}";
        $dma{'AUTHPATH'} = $authfile if exists $auth{'AUTHNAME'};
        $dma{'MASQUERADE'} = $mail{'MASQUERADE'} if $mail{'MASQUERADE'};

        &General::writehash($mailfile, \%mail);
        while (my ($k, $v) = each %dma) {
            print TXT "$k $v\n" if $k;
        }
        close TXT;
        close TXT1;
        $infomessage = "Settings saved successfully";
    } else {
        $cgiparams{'update'} = 'on';
        &configsite;
    }
} elsif ($action eq "Send test mail") {
    &testmail;
} elsif ($action eq "Upload GPG Key") {
    &import_key;
} elsif ($action eq "Delete GPG Key") {
    &delete_key;
} elsif ($action eq "Send Testmail encrypted") {
    &testmail(1);
}

&configsite;

sub configsite {
    # Update settings from CGI parameters if update is requested
    if (($cgiparams{'update'} // '') eq 'on') {
        $mail{'USEMAIL'} = $cgiparams{'USEMAIL'} // 'off';
        $mail{'SENDER'} = $cgiparams{'txt_mailsender'} // '';
        $mail{'RECIPIENT'} = $cgiparams{'txt_recipient'} // '';
        $mail{'MASQUERADE'} = $cgiparams{'txt_masquerade'} // '';
        $mail{'ENCRYPT'} = $cgiparams{'ENCRYPT'} // 'off';
        $mail{'GPG_KEY'} = $cgiparams{'GPG_KEY'} // '';
        $dma{'SMARTHOST'} = $cgiparams{'txt_mailserver'} // '';
        $dma{'PORT'} = $cgiparams{'txt_mailport'} // '';
        $auth{'AUTHNAME'} = $cgiparams{'txt_mailuser'} // '';
        $auth{'AUTHPASS'} = $cgiparams{'txt_mailpass'} // '';
        $auth{'AUTHHOST'} = $cgiparams{'txt_mailserver'} // '';
    }

    # Set checkbox and select states
    $checked{'usemail'}{'on'} = $mail{'USEMAIL'} eq 'on' ? 'CHECKED' : '';
    $selected{'mail_tls'}{'explicit'} = exists $dma{'STARTTLS'} ? 'selected' : '';
    $selected{'mail_tls'}{'implicit'} = (exists $dma{'SECURETRANSFER'} && !exists $dma{'STARTTLS'}) ? 'selected' : '';
    $selected{'mail_tls'}{'disabled'} = (!exists $dma{'SECURETRANSFER'} && !exists $dma{'STARTTLS'}) ? 'selected' : '';
    $checked{'encrypt'}{'on'} = $mail{'ENCRYPT'} eq 'on' ? 'CHECKED' : '';
    $mail{'SENDER'} //= '';
    $mail{'RECIPIENT'} //= '';
    $mail{'MASQUERADE'} //= '';
    $dma{'SMARTHOST'} //= '';
    $dma{'PORT'} //= '';
    $auth{'AUTHNAME'} //= '';
    $auth{'AUTHPASS'} //= '';

    # Debug: Log configuration settings
    warn "DEBUG: configsite: USEMAIL=$mail{'USEMAIL'}, SENDER=$mail{'SENDER'}, RECIPIENT=$mail{'RECIPIENT'}, MASQUERADE=$mail{'MASQUERADE'}, ENCRYPT=$mail{'ENCRYPT'}, GPG_KEY=$mail{'GPG_KEY'}\n";
    warn "DEBUG: configsite: SMARTHOST=$dma{'SMARTHOST'}, PORT=$dma{'PORT'}, AUTHNAME=$auth{'AUTHNAME'}, AUTHPASS=$auth{'AUTHPASS'}, AUTHHOST=$auth{'AUTHHOST'}\n";
    warn "DEBUG: configsite: checked{usemail}{on}=$checked{'usemail'}{'on'}, selected{mail_tls}{implicit}=$selected{'mail_tls'}{'implicit'}, selected{mail_tls}{explicit}=$selected{'mail_tls'}{'explicit'}, selected{mail_tls}{disabled}=$selected{'mail_tls'}{'disabled'}\n";

    # Render HTML page
    &Header::openpage("Mail Service", 1, '');
    &Header::openbigbox('100%', 'center');
    &error;
    &info;
    &Header::openbox('100%', 'left', "Mail Configuration");

    print <<END;
<script>
    \$(document).ready(function() {
        if (\$("#usemail").is(":checked")) {
            \$(".mailsrv").show();
        } else {
            \$(".mailsrv").hide();
        }
        \$("#usemail").change(function() {
            \$(".mailsrv").toggle();
        });
        if (\$("#encrypt").is(":checked")) {
            \$(".encrypt_opts").show();
        } else {
            \$(".encrypt_opts").hide();
        }
        \$("#encrypt").change(function() {
            \$(".encrypt_opts").toggle();
        });
    });
</script>
<form method='post' enctype='multipart/form-data' action='$ENV{'SCRIPT_NAME'}'>
<table width='100%' border='0'>
    <tr><th colspan='3'></th></tr>
    <tr>
        <td width='24em'>Activate Mail Service</td>
        <td><input type='checkbox' name='USEMAIL' id='usemail' $checked{'usemail'}{'on'}></td>
        <td></td>
    </tr>
</table><br>
<div class='mailsrv'>
    <table width='100%'>
        <tr>
            <td>Mail Sender<img src='/blob.gif' alt='*' /></td>
            <td><input type='text' name='txt_mailsender' value='$mail{'SENDER'}' style='width:22em;'></td>
        </tr>
        <tr>
            <td>Mail Recipient<img src='/blob.gif' alt='*' /></td>
            <td><input type='text' name='txt_recipient' value='$mail{'RECIPIENT'}' style='width:22em;'></td>
        </tr>
        <tr>
            <td>Masquerade Address</td>
            <td><input type='text' name='txt_masquerade' value='$mail{'MASQUERADE'}' style='width:22em;'></td>
        </tr>
        <tr>
            <td>Mail Server Address<img src='/blob.gif' alt='*' /></td>
            <td><input type='text' name='txt_mailserver' value='$dma{'SMARTHOST'}' style='width:22em;'></td>
        </tr>
        <tr>
            <td>Mail Server Port<img src='/blob.gif' alt='*' /></td>
            <td><input type='text' name='txt_mailport' value='$dma{'PORT'}' size='3'></td>
        </tr>
        <tr>
            <td>Mail Username</td>
            <td><input type='text' name='txt_mailuser' value='$auth{'AUTHNAME'}' style='width:22em;'></td>
        </tr>
        <tr>
            <td>Mail Password</td>
            <td><input type='password' name='txt_mailpass' value='$auth{'AUTHPASS'}' style='width:22em;'></td>
        </tr>
        <tr>
            <td>TLS mode</td>
            <td>
                <select name='mail_tls'>
                    <option value='implicit' $selected{'mail_tls'}{'implicit'}>Implicit (TLS)</option>
                    <option value='explicit' $selected{'mail_tls'}{'explicit'}>Explicit (STARTTLS)</option>
                    <option value='disabled' $selected{'mail_tls'}{'disabled'}>Disabled</option>
                </select>
            </td>
        </tr>
    </table>
END

    if (! -z $dmafile && $mail{'USEMAIL'} eq 'on') {
        print <<END;
<table width='100%'>
    <tr>
        <td></td>
        <td><input type='submit' name='ACTION' value='Send test mail'></td>
    </tr>
</table>
END
    }

    print <<END;
    <br><br><br>
    <table width='100%'>
        <tr>
            <td width='120px' style='margin-right: 1px; white-space: nowrap;'>Encrypt Mail</td>
            <td><input type='checkbox' name='ENCRYPT' id='encrypt' $checked{'encrypt'}{'on'}></td>
        </tr>
    </table>
    <div class='encrypt_opts'>
        <table width='100%'>
            <tr>
                <td>GPG Key</td>
                <td>
                    <select name='GPG_KEY'>
                        <option value=''>Select GPG Key</option>
END

    my @keys = &list_keys();
    foreach my $key (@keys) {
        my $sel = (defined $mail{'GPG_KEY'} && $mail{'GPG_KEY'} eq $key->{fingerprint}) ? 'selected' : '';
        my $fp = $key->{fingerprint} // '';
        my $uid = $key->{uid} // 'Unknown';
        my $expiry = $key->{expiry} // 'Never';
        print "<option value='$fp' $sel>$uid (Expiry Date: $expiry)</option>\n";
    }

    print <<END;
                    </select>
                </td>
            </tr>
            <tr>
                <td>Upload GPG Key</td>
                <td><input type='file' name='GPG_KEY_FILE'></td>
            </tr>
            <tr>
                <td></td>
                <td><input type='submit' name='ACTION' value='Upload GPG Key'></td>
            </tr>
        </table>
END

    if (! -z $dmafile && $mail{'USEMAIL'} eq 'on') {
        print <<END;
<table width='100%'>
    <tr>
        <td></td>
        <td><input type='submit' name='ACTION' value='Send Testmail encrypted'></td>
    </tr>
</table>
END
    }

    print <<END;
        <table width='100%'>
            <tr><th colspan='4'>GPG Key Management</th></tr>
            <tr>
                <td>Fingerprint</td>
                <td>Email</td>
                <td>Expiry Date</td>
                <td>Delete</td>
            </tr>
END

    foreach my $key (@keys) {
        my $expiry_status = $key->{expired} ? " style='color:red'" : ($key->{expires_soon} ? " style='color:orange'" : '');
        print "<tr><td>$key->{fingerprint}</td><td>$key->{uid}</td><td$expiry_status>$key->{expiry}</td><td><input type='checkbox' name='DELETE_KEY' value='$key->{fingerprint}'></td></tr>\n";
    }

    print <<END;
            <tr>
                <td colspan='4' align='right'><input type='submit' name='ACTION' value='Delete GPG Key'></td>
            </tr>
        </table>
    </div>
</div>
<table width='100%'>
    <tr>
        <td colspan='3' align='right'><input type='submit' name='ACTION' value='Save'></td>
    </tr>
</table>
</form>
END

    &Header::closebigbox();
    &Header::closepage();
    exit 0;
}

sub checkmailsettings {
    my $errormessage = '';
    if ($cgiparams{'txt_mailserver'} =~ /^(\d+)\.(\d+)\.(\d+)\.(\d+)$/) {
        if (!&General::validip($cgiparams{'txt_mailserver'})) {
            $errormessage .= "Invalid mail server IP address<br>";
        }
    } elsif ($cgiparams{'txt_mailserver'} && !&General::validfqdn($cgiparams{'txt_mailserver'})) {
        $errormessage .= "Invalid mail server FQDN<br>";
    }
    if (!$cgiparams{'txt_mailport'} || $cgiparams{'txt_mailport'} < 1 || $cgiparams{'txt_mailport'} > 65535) {
        $errormessage .= "Invalid mail server port<br>";
    }
    if (!$cgiparams{'txt_mailsender'}) {
        $errormessage .= "Sender email address cannot be empty<br>";
    } elsif (!&General::validemail($cgiparams{'txt_mailsender'})) {
        $errormessage .= "Invalid sender email address<br>";
    }
    if ($cgiparams{'txt_recipient'} && !&General::validemail($cgiparams{'txt_recipient'})) {
        $errormessage .= "Invalid recipient email address<br>";
    }
    if ($cgiparams{'txt_masquerade'} && !&General::validemail($cgiparams{'txt_masquerade'}) && !&General::validfqdn($cgiparams{'txt_masquerade'})) {
        $errormessage .= "Invalid masquerade address (must be valid email or hostname)<br>";
    }
    if (($cgiparams{'ENCRYPT'} // '') eq 'on' && !($cgiparams{'GPG_KEY'} // '')) {
        $errormessage .= "No GPG key selected for encryption<br>";
    }
    return $errormessage;
}

# Send a test mail (encrypted or unencrypted)
sub testmail {
    my ($encrypt) = @_;
    my $plaintext = $encrypt
        ? "This is the IPFire test mail but it is encrypted 8-) . Locked and loaded with GPG awesomeness!\n\n" .
          "To send an encrypted mail from the console, use:\n" .
          "echo -e \"Subject: Your Subject\\n\\nYour message here\" | /usr/sbin/sendmail.gpg recipient\\\@domain.com\n\n" .
          "Stay secure with IPFire!"
        : "This is the IPFire test mail.";

    my $sendmail_cmd = $encrypt ? '/usr/sbin/sendmail.gpg' : '/usr/sbin/sendmail.dma';
    my @sendmail_args = $encrypt ? () : ('-t'); # Parse recipients from headers
    # Set sender: Use MASQUERADE if set, otherwise SENDER, fallback to default
    if ($dma{'MASQUERADE'}) {
        push @sendmail_args, ('-f', $dma{'MASQUERADE'});
    } elsif ($mail{'SENDER'}) {
        push @sendmail_args, ('-f', $mail{'SENDER'});
    } else {
        push @sendmail_args, ('-f', 'nobody@ipfire.localdomain');
    }
    push @sendmail_args, $mail{'RECIPIENT'};
    warn "DEBUG: testmail: Executing: $sendmail_cmd @sendmail_args\n";

    open my $sendmail_fh, '|-', $sendmail_cmd, @sendmail_args or do {
        $errormessage = "Failed to open pipe to $sendmail_cmd: $!";
        warn "DEBUG: testmail: Failed to open pipe to $sendmail_cmd: $!\n";
        return;
    };
    if ($encrypt) {
        print $sendmail_fh "Subject: IPFire Encrypted Testmail\n\n";
        print $sendmail_fh $plaintext;
    } else {
        my $msg = MIME::Lite->new(
            From    => $dma{'MASQUERADE'} // $mail{'SENDER'} // 'nobody@ipfire.localdomain',
            To      => $mail{'RECIPIENT'},
            Subject => 'IPFire Testmail',
            Date    => strftime("%a, %d %b %Y %H:%M:%S %z", localtime),
            Type    => 'multipart/alternative',
        );
        $msg->attr('MIME-Version' => '1.0');
        $msg->attach(
            Type        => 'text/plain',
            Data        => $plaintext,
            Encoding    => '7bit',
            Disposition => 'inline',
        );
        print $sendmail_fh $msg->as_string;
    }
    close $sendmail_fh;

    if ($? == 0) {
        $infomessage = $encrypt ? "Encrypted test mail sent successfully" : "Test mail sent successfully";
        warn "DEBUG: testmail: " . ($encrypt ? "Encrypted test mail" : "Test mail") . " sent successfully\n";
    } else {
        $errormessage = "Failed to send test mail, exit code: $?";
        warn "DEBUG: testmail: Failed to send test mail, exit code: $?\n";
    }
}

# Import a GPG public key and validate it
sub import_key {
    my $filename = param('GPG_KEY_FILE') || '';
    if (!$filename) {
        $errormessage = "Upload failed: No file selected";
        return;
    }
    my ($fh, $temp_filename) = tempfile(DIR => '/tmp', SUFFIX => '.asc', UNLINK => 0);
    my $buffer;
    my $bytes_read = read(param('GPG_KEY_FILE'), $buffer, 1048576);
    if (!defined $bytes_read || $bytes_read <= 0) {
        $errormessage = "Upload failed: Failed to read file";
        unlink $temp_filename;
        return;
    }
    print $fh $buffer;
    close $fh;
    chmod 0600, $temp_filename;

    # Import key with trust-model always to bypass trust checks
    my $cmd = "/usr/bin/gpg --homedir $gpgdir --trust-model always --import $temp_filename 2>&1";
    my @output = `$cmd`;
    warn "DEBUG: import_key: GPG command: $cmd\n";
    warn "DEBUG: import_key: GPG output: " . join("\n", @output) . "\n";
    if ($? != 0) {
        $errormessage = "Invalid GPG key: " . join(" ", @output);
        unlink $temp_filename;
        return;
    }

    # Extract short key ID
    my $short_keyid = '';
    foreach my $line (@output) {
        if ($line =~ /key\s+([0-9A-F]{8}):/) {
            $short_keyid = $1;
        }
    }
    if (!$short_keyid) {
        $errormessage = "Failed to extract key ID";
        unlink $temp_filename;
        return;
    }

    # Retrieve full fingerprint and validate user ID
    my $fingerprint = '';
    my $has_userid = 0;
    my $recipient = $mail{'RECIPIENT'} // '';
    warn "DEBUG: import_key: Recipient: '$recipient'\n";
    my @list_output = `/usr/bin/gpg --homedir $gpgdir --list-keys --with-colons --with-fingerprint $short_keyid 2>&1`;
    warn "DEBUG: import_key: List keys command: /usr/bin/gpg --homedir $gpgdir --list-keys --with-colons --with-fingerprint $short_keyid 2>&1\n";
    warn "DEBUG: import_key: List keys output: " . join("\n", @list_output) . "\n";
    if ($recipient) {
        my $recipient_escaped = quotemeta($recipient);
        warn "DEBUG: import_key: Escaped recipient: '$recipient_escaped'\n";
        # Construct expected UID pattern (e.g., "p.pan1701 <p.pan1701@web.de>")
        my $uid_pattern = "p\.pan1701 <" . $recipient_escaped . ">";
        warn "DEBUG: import_key: UID pattern: '$uid_pattern'\n";
        foreach my $line (@list_output) {
            if ($line =~ /^fpr:::::::::([0-9A-F]{40}):/) {
                $fingerprint = $1;
                warn "DEBUG: import_key: Found fingerprint: '$fingerprint'\n";
            }
            if ($line =~ /^pub:.*:$uid_pattern:/) {
                $has_userid = 1;
                warn "DEBUG: import_key: Found user ID '$uid_pattern' in pub line: $line\n";
            }
        }
    }

    # Check if fingerprint and user ID are valid
    if (!$fingerprint) {
        $errormessage = "Failed to retrieve full fingerprint";
        unlink $temp_filename;
        return;
    }
    if (!$recipient) {
        $errormessage = "No recipient email configured";
        unlink $temp_filename;
        return;
    }
    if (!$has_userid) {
        $errormessage = "No valid user ID found for $recipient";
        unlink $temp_filename;
        return;
    }

    # Save fingerprint
    $mail{'GPG_KEY'} = $fingerprint;
    &General::writehash($mailfile, \%mail);
    $infomessage = "GPG key with fingerprint $fingerprint imported successfully";

    unlink $temp_filename;
}

sub delete_key {
    my $fingerprint = $cgiparams{'DELETE_KEY'} || '';
    if ($fingerprint =~ /^[0-9A-F]{40}$/) {
        my @output = `/usr/bin/gpg --homedir $gpgdir --batch --yes --delete-key '$fingerprint' 2>&1`;
        if ($? == 0) {
            $infomessage = "GPG key deleted successfully";
            if ($mail{'GPG_KEY'} eq $fingerprint) {
                $mail{'GPG_KEY'} = '';
                &General::writehash($mailfile, \%mail);
            }
        } else {
            $errormessage = "Delete failed: " . join(" ", @output);
        }
    } else {
        $errormessage = "Invalid GPG key";
    }
}

sub send_encrypted {
    if ($mail{'ENCRYPT'} ne 'on' || $mail{'USEMAIL'} ne 'on') {
        $errormessage = "Encryption not enabled or mail service not active";
        return;
    }
    if (!$mail{'GPG_KEY'}) {
        $errormessage = "No GPG key selected";
        return;
    }
    &testmail(1);
}

sub list_keys {
    my @keys;
    my @output = `/usr/bin/gpg --homedir $gpgdir --list-keys --with-colons --with-fingerprint 2>&1`;
    
    warn "DEBUG: list_keys: Total lines: " . scalar(@output) . "\n";
    
    my $current_key;
    foreach my $line (@output) {
        chomp $line if defined $line;
        my $line_safe = defined $line ? $line : 'undef';
        
        if ($line_safe =~ /^pub:[^:]*:[^:]*:[^:]*:[^:]*:[^:]*:([^:]*):[^:]*:[^:]*:(.*?):[^:]*:/) {
            my $expiry_str = $1 // '';
            my $uid_str = $2 // 'Unknown';
            $current_key = { 
                fingerprint => '', 
                uid => $uid_str, 
                expiry => 'Never', 
                expired => 0, 
                expires_soon => 0 
            };
            warn "DEBUG: list_keys: Found pub key, UID: '$uid_str', Expiry: '$expiry_str'\n";
            
            if ($expiry_str && $expiry_str =~ /^(\d{4})-(\d{2})-(\d{2})$/) {
                my ($year, $mon, $mday) = ($1, $2, $3);
                $current_key->{expiry} = sprintf("%04d-%02d-%02d", $year, $mon, $mday);
                my $expiry_time;
                eval {
                    $expiry_time = timelocal(0, 0, 0, $mday, $mon - 1, $year - 1900);
                    my $now = time();
                    $current_key->{expired} = $expiry_time < $now ? 1 : 0;
                    $current_key->{expires_soon} = ($expiry_time < $now + 7 * 86400 && $expiry_time >= $now) ? 1 : 0;
                    warn "DEBUG: list_keys: Expiry time: $expiry_time, Now: $now, Expired: $current_key->{expired}, Expires soon: $current_key->{expires_soon}\n";
                };
                if ($@) {
                    warn "DEBUG: list_keys: Error in timelocal for '$expiry_str': $@\n";
                }
            } else {
                warn "DEBUG: list_keys: Invalid or missing expiry date: '$expiry_str'\n";
            }
        } elsif ($line_safe =~ /^fpr:::::::::([0-9A-F]{40}):/) {
            my $fingerprint = $1;
            if ($current_key) {
                $current_key->{fingerprint} = $fingerprint;
                warn "DEBUG: list_keys: Found fingerprint: '$fingerprint'\n";
                if ($current_key->{fingerprint} && $current_key->{uid}) {
                    push @keys, { %$current_key };
                    warn "DEBUG: list_keys: Pushed key: '$current_key->{fingerprint}', UID: '$current_key->{uid}'\n";
                } else {
                    warn "DEBUG: list_keys: Skipping push, missing fingerprint or UID\n";
                }
                $current_key = undef;
            } else {
                warn "DEBUG: list_keys: Found fingerprint but no current_key defined\n";
            }
        }
    }
    warn "DEBUG: list_keys: Total keys found: " . scalar(@keys) . "\n";
    return @keys;
}

sub info {
    if ($infomessage) {
        &Header::openbox('100%', 'left', "Info Messages");
        print "<class name='base'>$infomessage\n";
        print "&nbsp;</class>\n";
        &Header::closebox();
    }
}

sub error {
    if ($errormessage) {
        &Header::openbox('100%', 'left', "Error Messages");
        print "<class name='base'>$errormessage\n";
        print "&nbsp;</class>\n";
        &Header::closebox();
    }
}
