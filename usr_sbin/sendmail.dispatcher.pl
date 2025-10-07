#!/usr/bin/perl
###############################################################################################################
# sendmail.dispatcher.pl - IPFire Mail Dispatcher (encrypted/plain router)                                    #
# Description: Dispatches sendmail calls based on mail.conf: ENCRYPT=on -> gpg.pl, else dma. Minimal overhead.#
# Usage: Standard sendmail calls (e.g., echo "Test" | /usr/sbin/sendmail user@domain.com)                     #
#        Automatically encrypts if ENCRYPT=on and GPG_KEY set in /var/ipfire/dma/mail.conf.                   #
# Requires: /var/ipfire/dma/mail.conf; gpg.pl for encryption.                                                 #
# License: GPLv3 - https://www.gnu.org/licenses/gpl-3.0.txt                                                   #
# Author: ummeegge (based on IPFire mail system)                                                              #
# Version: 1.0 (IPFire 2.27+; dynamic dispatching, zero warnings)                                             #
###############################################################################################################

use strict;
use warnings;

require '/var/ipfire/general-functions.pl';
no warnings 'once';  # Suppress "used only once" warnings for globals (IPFire style)

# Cache globals
my $swroot = $General::swroot;
my $mailfile = "${swroot}/dma/mail.conf";
my %mail = ();

# Read mail settings
&General::readhash($mailfile, \%mail) if (-f $mailfile);

# Determine dispatch: Encrypt if enabled and key present
my $encrypt = (($mail{'ENCRYPT'} || '') eq 'on') && $mail{'GPG_KEY'};
my $cmd = $encrypt ? '/usr/sbin/sendmail.gpg.pl' : '/usr/sbin/sendmail.dma';

warn "DEBUG: sendmail.dispatcher.pl: Dispatching to " . ($encrypt ? "encrypted path ($cmd)" : "plain path ($cmd)") . " (ENCRYPT=$mail{'ENCRYPT'})\n";

# Exec the chosen command with args
exec $cmd, @ARGV or do {
	warn "DEBUG: sendmail.dispatcher.pl: Failed to exec $cmd: $!\n";
	exit 1;
};
