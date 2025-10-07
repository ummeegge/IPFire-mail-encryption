#!/usr/bin/perl
###############################################################################
#                                                                             #
# IPFire.org - A linux based firewall                                         #
# Copyright (C) 2007-2025  IPFire Team  <info@ipfire.org>                     #
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

use MIME::Lite;
use CGI qw(param);
use File::Temp qw(tempfile);
use POSIX qw(strftime);
use Time::Local;

#enable only the following on debugging purpose
#use warnings;
#use CGI::Carp 'fatalsToBrowser';

require '/var/ipfire/general-functions.pl';
require "${General::swroot}/lang.pl";
require "${General::swroot}/header.pl";

#Initialize variables and hashes
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

#Read all parameters for site
&Header::getcgihash(\%cgiparams);
&General::readhash("${General::swroot}/main/settings", \%mainsettings);
&General::readhash("/srv/web/ipfire/html/themes/ipfire/include/colors.txt", \%color);

#Show Headers
&Header::showhttpheaders();

#Read configs (like original)
if (-f $dmafile) {
    open(FILE, "<", $dmafile) or die $!;
    foreach my $line (<FILE>) {
        $line =~ m/^([A-Z]+)\s+(.*)?$/;
        $dma{$1} = $2 if $1;
    }
    close FILE;
} else {
    open(FILE, ">$dmafile") or die $!;
    close FILE;
}

if (exists $dma{'AUTHPATH'} && -f $dma{'AUTHPATH'}) {
    open(FILE, "<", $dma{'AUTHPATH'}) or die $!;
    my $authline = <FILE>;
    close FILE;
    if ($authline) {
        my @part1 = split(/\|/,$authline);
        my @part2 = split(/\:/,$part1[1]);
        $auth{'AUTHNAME'} = $part1[0];
        $auth{'AUTHHOST'} = $part2[0];
        $auth{'AUTHPASS'} = $part2[1];
    }
}

if (-f $mailfile) {
    &General::readhash($mailfile, \%mail);
}

#Check GPG dir (early error, like original checks)
if (! -d $gpgdir) {
    $errormessage = "GPG key management: $gpgdir does not exist. Run install.sh.";
}

#ACTIONS (like original, but extended)
my $action = $cgiparams{'ACTION'} || '';
if ($action eq "$Lang::tr{'save'}") { #SaveButton
    $errormessage = &checkmailsettings();
    if (!$errormessage) {
        %auth=(); %dma=(); %mail=();
        open(TXT, ">$dmafile") or die $!;
        open(TXT1, ">$authfile") or die $!;
        open(TXT2, ">$mailfile") or die $!;
        close TXT2;

        $mail{'USEMAIL'} = $cgiparams{'USEMAIL'} || 'off';
        $mail{'SENDER'} = $cgiparams{'txt_mailsender'} || '';
        $mail{'RECIPIENT'} = $cgiparams{'txt_recipient'} || '';
        $mail{'MASQUERADE'} = $cgiparams{'txt_masquerade'} || '';
        $mail{'ENCRYPT'} = $cgiparams{'ENCRYPT'} || 'off';
        $mail{'GPG_KEY'} = $cgiparams{'GPG_KEY'} || '';

        if ($cgiparams{'txt_mailuser'} && $cgiparams{'txt_mailpass'}) {
            $auth{'AUTHNAME'} = &Header::escape($cgiparams{'txt_mailuser'});
            $auth{'AUTHPASS'} = &Header::escape($cgiparams{'txt_mailpass'});
            $auth{'AUTHHOST'} = $cgiparams{'txt_mailserver'};
            print TXT1 "$auth{'AUTHNAME'}|$auth{'AUTHHOST'}:$auth{'AUTHPASS'}\n";
        }

        $dma{'SMARTHOST'} = $cgiparams{'txt_mailserver'} || '';
        $dma{'PORT'} = $cgiparams{'txt_mailport'} || '';
        $dma{'STARTTLS'} = '' if ($cgiparams{'mail_tls'} eq 'explicit');
        $dma{'SECURETRANSFER'} = '' if ($cgiparams{'mail_tls'} eq 'explicit' || $cgiparams{'mail_tls'} eq 'implicit');
        $dma{'SPOOLDIR'} = "/var/spool/dma";
        $dma{'FULLBOUNCE'} = '';
        $dma{'MAILNAME'} = "$mainsettings{'HOSTNAME'}.$mainsettings{'DOMAINNAME'}";
        $dma{'AUTHPATH'} = $authfile if exists $auth{'AUTHNAME'};
        $dma{'MASQUERADE'} = $mail{'MASQUERADE'} if $mail{'MASQUERADE'};

        &General::writehash($mailfile, \%mail);
        while (my ($k,$v) = each %dma) {
            print TXT "$k $v\n" if $k;
        }
        close TXT; close TXT1;
        $infomessage = "Settings saved successfully";
    } else {
        $cgiparams{'update'}='on';
    }
} elsif ($action eq "$Lang::tr{'email testmail'}") {
    &testmail(0);  # unencrypted
} elsif ($action eq 'Send Testmail encrypted') {
    &testmail(1);  # encrypted
} elsif ($action eq "Upload GPG Key") {
    &import_key;
} elsif ($action eq "Delete GPG Key") {
    &delete_key;
}

#Show site
&configsite;

#FUNCTIONS
sub configsite {
    if ($cgiparams{'update'} eq 'on') {
        $mail{'USEMAIL'} = $cgiparams{'USEMAIL'} || 'off';
        $mail{'SENDER'} = $cgiparams{'txt_mailsender'} || '';
        $mail{'RECIPIENT'} = $cgiparams{'txt_recipient'} || '';
        $mail{'MASQUERADE'} = $cgiparams{'txt_masquerade'} || '';
        $mail{'ENCRYPT'} = $cgiparams{'ENCRYPT'} || 'off';
        $mail{'GPG_KEY'} = $cgiparams{'GPG_KEY'} || '';
        $dma{'SMARTHOST'} = $cgiparams{'txt_mailserver'} || '';
        $dma{'PORT'} = $cgiparams{'txt_mailport'} || '';
        $auth{'AUTHNAME'} = $cgiparams{'txt_mailuser'} || '';
        $auth{'AUTHPASS'} = $cgiparams{'txt_mailpass'} || '';
        $auth{'AUTHHOST'} = $cgiparams{'txt_mailserver'} || '';
    }

    $checked{'usemail'}{$mail{'USEMAIL'}} = 'CHECKED' if $mail{'USEMAIL'} eq 'on';
    $selected{'mail_tls'}{'explicit'} = 'selected' if exists $dma{'STARTTLS'};
    $selected{'mail_tls'}{'implicit'} = 'selected' if (exists $dma{'SECURETRANSFER'} && !exists $dma{'STARTTLS'});
    $selected{'mail_tls'}{'disabled'} = 'selected' if (!exists $dma{'SECURETRANSFER'} && !exists $dma{'STARTTLS'});
    $checked{'encrypt'}{'on'} = 'CHECKED' if $mail{'ENCRYPT'} eq 'on';

    &Header::openpage($Lang::tr{'email settings'}, 1, '');
    &Header::openbigbox('100%', 'center');
    &error; &info;
    &Header::openbox('100%', 'left', $Lang::tr{'email config'});

    print <<END;
<script>
\$(document).ready(function() {
    if (\$("#usemail").is(":checked")) { \$(".mailsrv").show(); } else { \$(".mailsrv").hide(); }
    \$("#usemail").change(function() { \$(".mailsrv").toggle(); });
    if (\$("#encrypt").is(":checked")) { \$(".encrypt_opts").show(); } else { \$(".encrypt_opts").hide(); }
    \$("#encrypt").change(function() { \$(".encrypt_opts").toggle(); });
});
</script>
<form method='post' enctype='multipart/form-data' action='$ENV{'SCRIPT_NAME'}'>
<table style='width:100%' border='0'>
<tr><th colspan='3'></th></tr>
<tr>
    <td style='width:24em'>$Lang::tr{'email usemail'}</td>
    <td><input type='checkbox' name='USEMAIL' id='usemail' $checked{'usemail'}{'on'}></td>
    <td></td>
</tr>
</table><br>
<div class="mailsrv">
<table style='width:100%'>
    <tr><td>$Lang::tr{'email mailsender'}<img src='/blob.gif' alt='*' /></td><td><input type='text' name='txt_mailsender' value='$mail{'SENDER'}' style='width:22em;'></td></tr>
    <tr><td>$Lang::tr{'email mailrcpt'}<img src='/blob.gif' alt='*' /></td><td><input type='text' name='txt_recipient' value='$mail{'RECIPIENT'}' style='width:22em;'></td></tr>
    <tr><td>Masquerade Address</td><td><input type='text' name='txt_masquerade' value='$mail{'MASQUERADE'}' style='width:22em;'></td></tr>
    <tr><td style='width:24em'>$Lang::tr{'email mailaddr'}<img src='/blob.gif' alt='*' /></td><td><input type='text' name='txt_mailserver' value='$dma{'SMARTHOST'}' style='width:22em;'></td></tr>
    <tr><td>$Lang::tr{'email mailport'}<img src='/blob.gif' alt='*' /></td><td><input type='text' name='txt_mailport' value='$dma{'PORT'}' size='3'></td></tr>
    <tr><td>$Lang::tr{'email mailuser'}</td><td><input type='text' name='txt_mailuser' value='@{[ &Header::escape($auth{'AUTHNAME'}) ]}' style='width:22em;'></td></tr>
    <tr><td>$Lang::tr{'email mailpass'}</td><td><input type='password' name='txt_mailpass' value='@{[ &Header::escape($auth{'AUTHPASS'}) ]}' style='width:22em;'></td></tr>
    <tr><td>$Lang::tr{'email tls'}</td><td>
        <select name='mail_tls'>
            <option value='implicit' $selected{'mail_tls'}{'implicit'}>$Lang::tr{'email tls implicit'}</option>
            <option value='explicit' $selected{'mail_tls'}{'explicit'}>$Lang::tr{'email tls explicit'}</option>
            <option value='disabled' $selected{'mail_tls'}{'disabled'}>$Lang::tr{'disabled'}</option>
        </select>
    </td></tr>
END

    if ($mail{'USEMAIL'} eq 'on' && -s $dmafile) {
        print "<tr><td></td><td><input type='submit' name='ACTION' value='$Lang::tr{'email testmail'}'></td></tr>";
    }

    print <<END;
</table></div><br><br>
<table style='width:100%'>
<tr><td width='120px'>Encrypt Mail</td><td><input type='checkbox' name='ENCRYPT' id='encrypt' $checked{'encrypt'}{'on'}></td></tr>
</table>
<div class="encrypt_opts">
<table style='width:100%'>
    <tr><td>GPG Key</td><td>
        <select name='GPG_KEY'>
            <option value=''>Select GPG Key</option>
END

    my @keys = &list_keys();
    foreach my $key (@keys) {
        my $sel = ($mail{'GPG_KEY'} eq $key->{fingerprint}) ? 'selected' : '';
        print "<option value='$key->{fingerprint}' $sel>$key->{uid} (Expiry: $key->{expiry})</option>\n";
    }

    print <<END;
        </select>
    </td></tr>
    <tr><td>Upload GPG Key</td><td><input type='file' name='GPG_KEY_FILE'></td></tr>
    <tr><td></td><td><input type='submit' name='ACTION' value='Upload GPG Key'></td></tr>
</table>
END

    if ($mail{'USEMAIL'} eq 'on' && -s $dmafile) {
        print "<table style='width:100%'><tr><td></td><td><input type='submit' name='ACTION' value='Send Testmail encrypted'></td></tr></table>";
    }

    print <<END;
<table style='width:100%'>
<tr><th colspan='4'>GPG Key Management</th></tr>
<tr><td>Fingerprint</td><td>Email</td><td>Expiry Date</td><td>Delete</td></tr>
END

    foreach my $key (@keys) {
        my $style = $key->{expired} ? " style='color:red'" : ($key->{expires_soon} ? " style='color:orange'" : '');
        print "<tr><td>$key->{fingerprint}</td><td>$key->{uid}</td><td$style>$key->{expiry}</td><td><input type='checkbox' name='DELETE_KEY' value='$key->{fingerprint}'></td></tr>\n";
    }

    print <<END;
<tr><td colspan='4' align='right'><input type='submit' name='ACTION' value='Delete GPG Key'></td></tr>
</table></div>
<table style='width:100%'><tr><td colspan='3' align='right'><input type='submit' name='ACTION' value='$Lang::tr{'save'}'></td></tr></table>
</form>
END
    &Header::closebox(); &Header::openbigbox(); &Header::closepage();
    exit 0;
}

sub checkmailsettings {
    my $error = '';
    if ($cgiparams{'txt_mailserver'} =~ /^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$/) {
        $error .= $Lang::tr{'email invalid mailip'} . "<br>" unless &General::validip($cgiparams{'txt_mailserver'});
    } elsif ($cgiparams{'txt_mailserver'} && !&General::validfqdn($cgiparams{'txt_mailserver'})) {
        $error .= $Lang::tr{'email invalid mailfqdn'} . "<br>";
    }
    if (!$cgiparams{'txt_mailport'} || $cgiparams{'txt_mailport'} < 1 || $cgiparams{'txt_mailport'} > 65535) {
        $error .= $Lang::tr{'email invalid mailport'} . "<br>";
    }
    if (!$cgiparams{'txt_mailsender'} || !&General::validemail($cgiparams{'txt_mailsender'})) {
        $error .= $Lang::tr{'email invalid'} . " $Lang::tr{'email mailsender'}<br>";
    }
    if ($cgiparams{'txt_recipient'} && !&General::validemail($cgiparams{'txt_recipient'})) {
        $error .= $Lang::tr{'email recipient invalid'} . "<br>";
    }
    if ($cgiparams{'txt_masquerade'} && !&General::validemail($cgiparams{'txt_masquerade'}) && !&General::validfqdn($cgiparams{'txt_masquerade'})) {
        $error .= "Invalid masquerade address<br>";
    }
    if (($cgiparams{'ENCRYPT'} || '') eq 'on' && !$cgiparams{'GPG_KEY'}) {
        $error .= "No GPG key selected for encryption<br>";
    }
    return $error;
}

sub testmail {
    my ($encrypt) = @_;
    my $plaintext = $encrypt ? "This is the IPFire test mail but it is encrypted 8-) . Locked and loaded with GPG awesomeness!\n\nTo send an encrypted mail from the console, use:\n echo -e \"Subject: Your Subject\\n\\nYour message here\" | /usr/sbin/sendmail recipient@domain.com\n\nStay secure with IPFire!" : "This is the IPFire test mail.";
    my $cmd = '/usr/sbin/sendmail';  # Dispatcher for auto routing
    my @args = ('-t', '-f', ($dma{'MASQUERADE'} || $mail{'SENDER'} || 'nobody@ipfire.localdomain'), $mail{'RECIPIENT'});
    open(SENDMAIL, "|-", $cmd, @args) or do { $errormessage = "Failed to open pipe to $cmd: $!"; return; };
    if ($encrypt) {
        print SENDMAIL "Subject: IPFire Encrypted Testmail\n\n$plaintext";
    } else {
        my $msg = MIME::Lite->new(From => $dma{'MASQUERADE'} || $mail{'SENDER'} || 'nobody@ipfire.localdomain', To => $mail{'RECIPIENT'}, Subject => 'IPFire Testmail', Date => strftime("%a, %d %b %Y %H:%M:%S %z", localtime), Type => 'text/plain', Data => $plaintext);
        print SENDMAIL $msg->as_string;
    }
    close SENDMAIL;
    $infomessage = $encrypt ? "Encrypted test mail sent successfully" : "Test mail sent successfully" if $? == 0;
    $errormessage = "Failed to send test mail, exit code: $?" if $? != 0;
}

sub get_gpg_version {
    my $version_output = `/usr/bin/gpg --version 2>&1`;
    if ($version_output =~ /gpg \(GnuPG\) (\d+\.\d+)/) {
        return $1;
    }
    return "2.4"; # Default to 2.4 if version detection fails
}

sub import_key {
    my $fh = param('GPG_KEY_FILE') or do { $errormessage = "No file selected"; return; };
    my ($tmpfh, $tmpfile) = tempfile(DIR => '/tmp', SUFFIX => '.asc');
    my $buffer;
    read($fh, $buffer, 1048576) or do { $errormessage = "Failed to read file"; unlink $tmpfile; return; };
    print $tmpfh $buffer; close $tmpfh; chmod 0600, $tmpfile;

    my $cmd = "/usr/bin/gpg --homedir $gpgdir --no-permission-warning --trust-model always --import $tmpfile 2>&1";
    my @output = `$cmd`;
    warn "DEBUG: import_key: GPG command: $cmd\n";
    warn "DEBUG: import_key: GPG output: " . join("\n", @output) . "\n";
    if ($? != 0 && !grep(/imported:|unchanged:/, @output)) {
        $errormessage = "Invalid GPG key: " . join(" ", @output);
        unlink $tmpfile; return;
    }

    my $short_keyid = '';
    foreach my $line (@output) {
        if ($line =~ /key\s+([0-9A-F]{8,16}):/) {
            $short_keyid = $1;
            last;
        }
    }
    if (!$short_keyid) {
        $errormessage = "Failed to extract key ID";
        unlink $tmpfile;
        return;
    }

    my $fingerprint = '';
    my $match = 0;
    my $recipient = $mail{'RECIPIENT'} || '';
    my $gpg_version = &get_gpg_version();
    warn "DEBUG: import_key: GPG version: $gpg_version\n";
    if ($recipient) {
        my $recipient_escaped = quotemeta($recipient);
        my @list_output = `/usr/bin/gpg --homedir $gpgdir --no-permission-warning --list-keys --with-colons --with-fingerprint $short_keyid 2>&1`;
        warn "DEBUG: import_key: List keys output: " . join("\n", @list_output) . "\n";
        foreach my $line (@list_output) {
            my @fields = split(/:/, $line);
            warn "DEBUG: import_key: Processing line: $line\n";
            if ($fields[0] eq 'fpr') {
                $fingerprint = $fields[9];
                warn "DEBUG: import_key: Found fingerprint: $fingerprint\n";
            }
            if ($gpg_version =~ /^1\.4/) {
                if ($fields[0] eq 'pub' && $fields[8] && $fields[8] ne '' && $fields[8] =~ /${recipient_escaped}/) {
                    $match = 1;
                    warn "DEBUG: import_key: GPG 1.4 - Matched UID in pub: $fields[8]\n";
                }
            } else {
                if ($fields[0] eq 'uid' && $fields[9] && $fields[9] =~ /${recipient_escaped}/) {
                    $match = 1;
                    warn "DEBUG: import_key: GPG 2.4 - Matched UID: $fields[9]\n";
                }
            }
        }
        if (!$fingerprint) {
            $errormessage = "Failed to retrieve full fingerprint";
            unlink $tmpfile;
            return;
        }
        if (!$match) {
            $errormessage = "No valid user ID for $recipient";
            unlink $tmpfile;
            return;
        }
    } else {
        $errormessage = "No recipient configured";
        unlink $tmpfile;
        return;
    }

    $mail{'GPG_KEY'} = $fingerprint;
    &General::writehash($mailfile, \%mail);
    $infomessage = "GPG key $fingerprint imported successfully";
    unlink $tmpfile;
}

sub delete_key {
    my @to_delete = (ref(param('DELETE_KEY')) eq 'ARRAY') ? @{param('DELETE_KEY')} : (param('DELETE_KEY') // ());
    if (!@to_delete) {
        $errormessage = "No GPG key selected for deletion";
        return;
    }
    foreach my $fp (@to_delete) {
        next unless $fp =~ /^[0-9A-F]{40}$/;
        my @output = `/usr/bin/gpg --homedir $gpgdir --no-permission-warning --batch --yes --delete-key '$fp' 2>&1`;
        warn "DEBUG: delete_key: Deleting key $fp, output: " . join("\n", @output) . "\n";
        if ($? == 0) {
            $infomessage .= "GPG key $fp deleted successfully<br>";
            if ($mail{'GPG_KEY'} eq $fp) {
                $mail{'GPG_KEY'} = '';
                &General::writehash($mailfile, \%mail);
            }
        } else {
            $errormessage .= "Failed to delete GPG key $fp: " . join(" ", @output) . "<br>";
            if (grep /Permission denied/, @output) {
                $errormessage .= "Check permissions on $gpgdir (must be owned by nobody:nobody with write access)<br>";
            }
        }
    }
}

sub list_keys {
    my @keys;
    my @output = `/usr/bin/gpg --homedir $gpgdir --no-permission-warning --list-keys --with-colons --with-fingerprint 2>&1`;
    my $gpg_version = &get_gpg_version();
    warn "DEBUG: list_keys: GPG version: $gpg_version\n";
    warn "DEBUG: list_keys: Total lines: " . scalar(@output) . "\n";

    my $current_key = undef;
    foreach my $line (@output) {
        chomp $line;
        my @fields = split(/:/, $line);
        warn "DEBUG: list_keys: Processing line: $line\n";
        warn "DEBUG: list_keys: Pub fields: " . join("|", @fields) . "\n" if $fields[0] eq 'pub';
        if ($gpg_version =~ /^1\.4/) {
            if ($fields[0] eq 'pub') {
                if ($current_key && $current_key->{fingerprint} && $current_key->{uid} ne 'Unknown') {
                    push @keys, { %$current_key };
                    warn "DEBUG: list_keys: GPG 1.4 - Pushed key: $current_key->{fingerprint}, UID: $current_key->{uid}, Expiry: $current_key->{expiry}\n";
                }
                my $exp = $fields[6] // '';
                my $uid = ($fields[8] && $fields[8] ne '') ? $fields[8] : 'Unknown';
                warn "DEBUG: list_keys: GPG 1.4 - Raw UID: '$fields[8]', Parsed UID: '$uid'\n";
                my $expiry;
                my $timestamp;
                if ($exp =~ /^(\d{4})-(\d{2})-(\d{2})$/) {
                    eval {
                        $timestamp = timelocal(0, 0, 0, $3, $2 - 1, $1 - 1900);
                        $expiry = strftime("%Y-%m-%d", localtime($timestamp));
                    };
                    if ($@) {
                        warn "DEBUG: list_keys: GPG 1.4 - Failed to parse expiry date '$exp': $@\n";
                        $expiry = 'Never';
                    }
                } else {
                    $expiry = 'Never';
                }
                $current_key = { fingerprint => '', uid => $uid, expiry => $expiry, expired => 0, expires_soon => 0 };
                warn "DEBUG: list_keys: GPG 1.4 - Found pub, UID: $uid, Raw expiry: '$exp', Formatted expiry: $expiry\n";
                if ($timestamp && $timestamp > 0) {
                    my $now = time;
                    $current_key->{expired} = ($timestamp < $now) ? 1 : 0;
                    $current_key->{expires_soon} = ($timestamp < $now + 7*86400 && $timestamp >= $now) ? 1 : 0;
                    warn "DEBUG: list_keys: GPG 1.4 - Expiry timestamp: $timestamp, Now: $now, Expired: $current_key->{expired}, Expires soon: $current_key->{expires_soon}\n";
                } else {
                    warn "DEBUG: list_keys: GPG 1.4 - No valid expiry timestamp, set to Never\n";
                }
            } elsif ($fields[0] eq 'fpr' && $current_key) {
                $current_key->{fingerprint} = $fields[9];
                warn "DEBUG: list_keys: GPG 1.4 - Found fingerprint: $current_key->{fingerprint}\n";
                if ($current_key->{uid} ne 'Unknown') {
                    push @keys, { %$current_key };
                    warn "DEBUG: list_keys: GPG 1.4 - Pushed key: $current_key->{fingerprint}, UID: $current_key->{uid}, Expiry: $current_key->{expiry}\n";
                }
            }
        } else {
            if ($fields[0] eq 'pub') {
                if ($current_key && $current_key->{fingerprint} && $current_key->{uid} ne 'Unknown') {
                    push @keys, { %$current_key };
                    warn "DEBUG: list_keys: GPG 2.4 - Pushed key: $current_key->{fingerprint}, UID: $current_key->{uid}, Expiry: $current_key->{expiry}\n";
                }
                my $exp = $fields[6] // '';
                my $expiry = ($exp && $exp =~ /^\d+$/) ? strftime("%Y-%m-%d", localtime($exp)) : 'Never';
                $current_key = { fingerprint => '', uid => 'Unknown', expiry => $expiry, expired => 0, expires_soon => 0 };
                warn "DEBUG: list_keys: GPG 2.4 - Found pub, Raw expiry: '$exp', Formatted expiry: $expiry\n";
                if ($exp && $exp =~ /^\d+$/) {
                    my $now = time;
                    $current_key->{expired} = ($exp < $now) ? 1 : 0;
                    $current_key->{expires_soon} = ($exp < $now + 7*86400 && $exp >= $now) ? 1 : 0;
                    warn "DEBUG: list_keys: GPG 2.4 - Expiry timestamp: $exp, Now: $now, Expired: $current_key->{expired}, Expires soon: $current_key->{expires_soon}\n";
                } else {
                    warn "DEBUG: list_keys: GPG 2.4 - No valid expiry timestamp, set to Never\n";
                }
            } elsif ($fields[0] eq 'uid' && $current_key) {
                $current_key->{uid} = $fields[9] || 'Unknown';
                warn "DEBUG: list_keys: GPG 2.4 - Found UID: $current_key->{uid}\n";
            } elsif ($fields[0] eq 'fpr' && $current_key) {
                $current_key->{fingerprint} = $fields[9];
                warn "DEBUG: list_keys: GPG 2.4 - Found fingerprint: $current_key->{fingerprint}\n";
                if ($current_key->{uid} ne 'Unknown') {
                    push @keys, { %$current_key };
                    warn "DEBUG: list_keys: GPG 2.4 - Pushed key: $current_key->{fingerprint}, UID: $current_key->{uid}, Expiry: $current_key->{expiry}\n";
                }
            }
        }
    }
    warn "DEBUG: list_keys: Total keys found: " . scalar(@keys) . "\n";
    return @keys;
}

sub error {
    if ($errormessage) {
        &Header::openbox('100%', 'left', $Lang::tr{'error messages'});
        print "<div class='base'>$errormessage</div>\n";
        &Header::closebox();
    }
}

sub info {
    if ($infomessage) {
        &Header::openbox('100%', 'left', $Lang::tr{'info messages'});
        print "<div class='base'>$infomessage</div>\n";
        &Header::closebox();
    }
}
