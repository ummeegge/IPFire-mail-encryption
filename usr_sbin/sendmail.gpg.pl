#!/usr/bin/perl

###############################################################################################################
# sendmail.gpg.pl - IPFire GPG-Encrypted Mail Wrapper                                                         #
# Description: This script wraps DMA sendmail to enable GPG encryption for IPFire emails.                     #
# Usage:                                                                                                      #
#   - Encrypted: echo -e "Subject: Test\n\nMessage" | /usr/sbin/sendmail.gpg recipient@domain.com             #
#   - Recipient from @ARGV, Sender from /var/ipfire/dma/mail.conf, Encryption if ENCRYPT=on and GPG_KEY set.  #
#   - For logs: grep error /var/log/messages | /usr/sbin/sendmail.gpg admin@domain.com                        #
#   - Requires: ENCRYPT=on, GPG_KEY in mail.conf, GPG keys in /var/ipfire/dma/encryption                      #
#                                                                                                             #
# License: GPLv3 - See https://www.gnu.org/licenses/gpl-3.0.txt for details.                                  #
# Author: ummeegge (based on IPFire mail.cgi enhancements)                                                    #
# Version: 1.0 (IPFire 2.27+ compatible)                                                                      #
###############################################################################################################

use strict;
use warnings;
use MIME::Lite;
use File::Temp qw(tempfile);
use POSIX qw(strftime);

require '/var/ipfire/general-functions.pl';

my $mailfile = "${General::swroot}/dma/mail.conf";
my $gpgdir = "${General::swroot}/dma/encryption";
my %mail = ();

# Read mail settings
&General::readhash($mailfile, \%mail) if -f $mailfile;
warn "DEBUG: sendmail.gpg: Loaded mail settings: ENCRYPT=$mail{'ENCRYPT'}, GPG_KEY=$mail{'GPG_KEY'}, SENDER=$mail{'SENDER'}\n";

# Read mail from STDIN
my $mail_data = do { local $/; <STDIN> };
warn "DEBUG: sendmail.gpg: Received mail data (length: " . length($mail_data) . " bytes):\n$mail_data\n";

# Parse recipients from command-line arguments
my @recipients;
foreach my $arg (@ARGV) {
    if ($arg =~ /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/) {
        push @recipients, $arg;
    }
}
unless (@recipients) {
    warn "DEBUG: sendmail.gpg: No valid recipients found in arguments (@ARGV)\n";
    exit 1;
}
warn "DEBUG: sendmail.gpg: Recipients: @recipients\n";

# Parse input to separate headers (e.g., Subject:) from body
my %extra_headers;
my $body = '';
my @lines = split /\n/, $mail_data;
my $in_headers = 1;
foreach my $line (@lines) {
    if ($in_headers && $line =~ /^(\S+):\s*(.*)$/) {
        $extra_headers{$1} = $2;
    } else {
        $in_headers = 0;
        $body .= "$line\n" unless $line =~ /^$/;
    }
}
warn "DEBUG: sendmail.gpg: Extracted extra headers: " . join(', ', keys %extra_headers) . "\n";
warn "DEBUG: sendmail.gpg: Body length: " . length($body) . " bytes\n";

# Create MIME::Lite message
my $msg = MIME::Lite->new(
    From    => $mail{'SENDER'} // 'nobody@ipfire.localdomain',
    To      => join(',', @recipients),
    Subject => $extra_headers{'Subject'} // 'IPFire Mail',
    Date    => strftime("%a, %d %b %Y %H:%M:%S %z", localtime),
    Type    => 'multipart/encrypted; protocol="application/pgp-encrypted"',
);
$msg->attr('MIME-Version' => '1.0');

# Encrypt if enabled (only the body!)
if ($mail{'ENCRYPT'} eq 'on' && $mail{'GPG_KEY'}) {
    warn "DEBUG: sendmail.gpg: Encryption enabled, using GPG key: $mail{'GPG_KEY'}\n";

    # Pack the body into a text/plain MIME structure before encryption
    my $plain_msg = MIME::Lite->new(
        Type    => 'text/plain',
        Data    => $body,
        Encoding => '7bit',
    );
    $plain_msg->attr('MIME-Version' => '1.0');
    $plain_msg->attr('Content-Disposition' => 'inline');
    my $plain_string = $plain_msg->as_string;

    # Encrypt the MIME-wrapped body
    my ($fh, $plain_file) = tempfile(DIR => '/tmp', SUFFIX => '.txt', UNLINK => 0);
    print $fh $plain_string;
    close $fh;
    chmod 0600, $plain_file;
    my $encrypted_file = "$plain_file.asc";
    my @output = `/usr/bin/gpg --homedir $gpgdir --trust-model always --armor --encrypt --recipient '$mail{'GPG_KEY'}' --output $encrypted_file $plain_file 2>&1`;
    if ($? != 0) {
        warn "DEBUG: sendmail.gpg: Encryption failed: " . join(" ", @output) . "\n";
        unlink $plain_file;
        exit 1;
    }
    open(my $enc_fh, '<', $encrypted_file) or do {
        warn "DEBUG: sendmail.gpg: Failed to read encrypted file: $!\n";
        unlink $plain_file;
        unlink $encrypted_file;
        exit 1;
    };
    my $encrypted_data = do { local $/; <$enc_fh> };
    close $enc_fh;
    unlink $plain_file;
    unlink $encrypted_file;

    $msg->attach(
        Type        => 'application/pgp-encrypted',
        Data        => "Version: 1\n",
        Encoding    => '7bit',
        Disposition => 'inline',
    );
    $msg->attach(
        Type        => 'application/octet-stream',
        Data        => $encrypted_data,
        Encoding    => '7bit',
        Disposition => 'inline',
        Filename    => 'encrypted.asc',
        Description => 'OpenPGP encrypted message',
    );
    warn "DEBUG: sendmail.gpg: Encrypted mail prepared (body only)\n";
} else {
    $msg->attr('Content-Type' => 'multipart/alternative');
    $msg->attach(
        Type        => 'text/plain',
        Data        => $body,
        Encoding    => '7bit',
        Disposition => 'inline',
    );
    warn "DEBUG: sendmail.gpg: Plaintext mail prepared\n";
}

# Debug: Save the raw email to a file
my $debug_email_file = "/tmp/sent_email_".time().".eml";
open my $debug_fh, '>', $debug_email_file or do {
    warn "DEBUG: sendmail.gpg: Failed to save debug email to $debug_email_file: $!\n";
};
print $debug_fh $msg->as_string;
close $debug_fh;
warn "DEBUG: sendmail.gpg: Saved raw email to $debug_email_file\n";

# Send the mail using dma's original sendmail
my $sendmail_cmd = '/usr/sbin/sendmail.dma';
my @sendmail_args = ('-f', $mail{'SENDER'}, @recipients);
warn "DEBUG: sendmail.gpg: Executing: $sendmail_cmd @sendmail_args\n";

open my $sendmail_fh, '|-', $sendmail_cmd, @sendmail_args or do {
    warn "DEBUG: sendmail.gpg: Failed to open pipe to $sendmail_cmd: $!\n";
    exit 1;
};
print $sendmail_fh $msg->as_string;
close $sendmail_fh;

if ($? == 0) {
    warn "DEBUG: sendmail.gpg: Mail sent successfully\n";
    exit 0;
} else {
    warn "DEBUG: sendmail.gpg: Failed to send mail, exit code: $?\n";
    exit 1;
}
