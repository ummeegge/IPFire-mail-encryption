#!/usr/bin/perl
###############################################################################################################
# sendmail.gpg.pl - IPFire GPG-Encrypted Mail Wrapper (optimized, IPFire-style)                              #
# Description: Wraps DMA sendmail for GPG encryption. Parses STDIN, encrypts body if enabled, sends via DMA.  #
# Usage: echo -e "Subject: Test\n\nMessage" | /usr/sbin/sendmail recipient@domain.com                        #
# Requires: ENCRYPT=on and GPG_KEY in /var/ipfire/dma/mail.conf; keys in /var/ipfire/dma/encryption.         #
# License: GPLv3 - https://www.gnu.org/licenses/gpl-3.0.txt                                                   #
# Author: ummeegge (based on IPFire mail.cgi)                                                                 #
# Version: 1.2 (IPFire 2.27+; re-read mail.conf before encryption)                                           #
###############################################################################################################

use strict;
use warnings;
use MIME::Lite;
use File::Temp qw(tempfile);
use POSIX qw(strftime);
use File::stat;

require '/var/ipfire/general-functions.pl';
no warnings 'once';  # Suppress "used only once" warnings for globals (e.g., swroot)

# Cache globals (IPFire style)
my $swroot = $General::swroot;
my $mailfile = "${swroot}/dma/mail.conf";
my $gpgdir = "${swroot}/dma/encryption";
my %mail = ();

# Read mail settings initially
&General::readhash($mailfile, \%mail) if (-f $mailfile);
my $last_mtime = (-f $mailfile) ? stat($mailfile)->mtime : 0;
warn "DEBUG: sendmail.gpg.pl: Loaded mail settings: ENCRYPT=$mail{'ENCRYPT'}, GPG_KEY=$mail{'GPG_KEY'}, SENDER=$mail{'SENDER'}, mtime=$last_mtime\n";

# Read mail from STDIN
my $mail_data = do { local $/; <STDIN> };
warn "DEBUG: sendmail.gpg.pl: Received mail data (length: " . length($mail_data) . " bytes)\n";

# Parse recipients from @ARGV
my @recipients = ();
foreach my $arg (@ARGV) {
	if ($arg =~ /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/) {
		push @recipients, $arg;
	}
}
unless (@recipients) {
	warn "DEBUG: sendmail.gpg.pl: No valid recipients found in arguments (@ARGV)\n";
	exit 1;
}
warn "DEBUG: sendmail.gpg.pl: Recipients: @recipients\n";

# Parse headers and body
my %headers = ();
my $body = '';
my @lines = split /\n/, $mail_data;
my $in_headers = 1;
foreach my $line (@lines) {
	if ($in_headers && $line =~ /^(\S+):\s*(.*)$/) {
		$headers{$1} = $2;
	} else {
		$in_headers = 0;
		$body .= "$line\n" unless ($line =~ /^$/);
	}
}
warn "DEBUG: sendmail.gpg.pl: Extracted headers: " . join(', ', keys %headers) . ", body length: " . length($body) . "\n";

# Re-read mail.conf if modified
if (-f $mailfile) {
	my $current_mtime = stat($mailfile)->mtime;
	if ($current_mtime > $last_mtime) {
		%mail = ();
		&General::readhash($mailfile, \%mail);
		warn "DEBUG: sendmail.gpg.pl: Reloaded mail settings due to file change: ENCRYPT=$mail{'ENCRYPT'}, GPG_KEY=$mail{'GPG_KEY'}, SENDER=$mail{'SENDER'}, new mtime=$current_mtime\n";
	}
}

# Build MIME message
my $from = $mail{'MASQUERADE'} || $mail{'SENDER'} || 'nobody@ipfire.localdomain';
my $msg = MIME::Lite->new(
	From    => $from,
	To      => join(',', @recipients),
	Subject => $headers{'Subject'} || 'IPFire Mail',
	Date    => strftime("%a, %d %b %Y %H:%M:%S %z", localtime),
	Type    => 'multipart/encrypted; protocol="application/pgp-encrypted"',
);
$msg->attr('MIME-Version' => '1.0');

# Encrypt if enabled
if ($mail{'ENCRYPT'} eq 'on' && $mail{'GPG_KEY'}) {
	warn "DEBUG: sendmail.gpg.pl: Encryption enabled, using GPG key: $mail{'GPG_KEY'}\n";

	# Wrap body in MIME text/plain
	my $plain_msg = MIME::Lite->new(
		Type     => 'text/plain',
		Data     => $body,
		Encoding => '7bit',
	);
	$plain_msg->attr('MIME-Version' => '1.0');
	$plain_msg->attr('Content-Disposition' => 'inline');
	my $plain_string = $plain_msg->as_string;

	# Temp files for encryption
	my ($fh, $plain_file) = tempfile(DIR => '/tmp', SUFFIX => '.txt', UNLINK => 0);
	print $fh $plain_string;
	close $fh;
	chmod 0600, $plain_file;
	my $encrypted_file = "$plain_file.asc";

	# GPG encrypt (redirect stderr to suppress warnings)
	my $gpg_cmd = "/usr/bin/gpg --homedir $gpgdir --trust-model always --armor --encrypt --quiet --recipient '$mail{'GPG_KEY'}' --output $encrypted_file $plain_file 2>/dev/null";
	system($gpg_cmd) == 0 or do {
		warn "DEBUG: sendmail.gpg.pl: GPG encryption failed for $mail{'GPG_KEY'} (check key/permissions)\n";
		unlink $plain_file;
		exit 1;
	};
	warn "DEBUG: sendmail.gpg.pl: Body encrypted successfully with key $mail{'GPG_KEY'}\n";

	# Read encrypted data
	open(my $enc_fh, '<', $encrypted_file) or do {
		warn "DEBUG: sendmail.gpg.pl: Failed to read encrypted file: $!\n";
		unlink $plain_file, $encrypted_file;
		exit 1;
	};
	my $encrypted_data = do { local $/; <$enc_fh> };
	close $enc_fh;
	unlink $plain_file, $encrypted_file;

	# Attach encrypted parts
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
	warn "DEBUG: sendmail.gpg.pl: Encrypted mail prepared (body only)\n";
} else {
	$msg->attr('Content-Type' => 'text/plain');
	$msg->replace('Data', $body);
	warn "DEBUG: sendmail.gpg.pl: Plaintext mail prepared (encryption disabled or no GPG_KEY)\n";
}

# Optional debug: Save raw email
my $debug_email_file = "/tmp/sent_email_" . time() . ".eml";
open(my $debug_fh, '>', $debug_email_file) or warn "DEBUG: sendmail.gpg.pl: Failed to save debug email: $!\n";
print $debug_fh $msg->as_string;
close $debug_fh;
warn "DEBUG: sendmail.gpg.pl: Saved raw email to $debug_email_file\n";

# Send via DMA
my $sendmail_cmd = '/usr/sbin/sendmail.dma';
my @sendmail_args = ('-f', $from, @recipients);
warn "DEBUG: sendmail.gpg.pl: Executing: $sendmail_cmd @sendmail_args\n";

open(my $sendmail_fh, '|-', $sendmail_cmd, @sendmail_args) or do {
	warn "DEBUG: sendmail.gpg.pl: Failed to open pipe to $sendmail_cmd: $!\n";
	exit 1;
};
print $sendmail_fh $msg->as_string;
close $sendmail_fh;

if ($? == 0) {
	warn "DEBUG: sendmail.gpg.pl: Mail sent successfully to @recipients (from $from)\n";
	exit 0;
} else {
	warn "DEBUG: sendmail.gpg.pl: Failed to send mail, exit code: $?\n";
	exit 1;
}

# EOF
