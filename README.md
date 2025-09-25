# IPFire Mail Encryption Addon

This addon enhances IPFire's `mail.cgi` with GPG encryption and masquerade support, enabling secure email delivery for logs, alerts, and test mails via the Web User Interface (WUI) or command line.

## Features

- **GPG Encryption**: Send encrypted emails using GPG keys, configured via WUI or command line.
- **Masquerade Option**: Set an alternative sender address (email or hostname) for outgoing emails.
- **GPG Key Management**: Upload, view, and delete GPG keys in the WUI.
- **Test Mail**: Send unencrypted or encrypted test emails from the WUI.
- **Command-Line Support**: Pipe logs or messages to `/usr/sbin/sendmail.gpg` for encrypted delivery.
- **Debugging**: Detailed logs in `/var/log/httpd/error_log` and `/tmp/sent_email_*.eml`.

## Prerequisites

- IPFire 2.27+ (Core Update 185 or later recommended).
- GPG (`/usr/bin/gpg`), `MIME::Lite`, and `sendmail.dma` already installed.
- GPG key directory: `/var/ipfire/dma/encryption` (must exist).

## Installation

Manual installation (installer script coming soon):
1. Most important, make a Backup of the existing /srv/web/ipfire/cgi-bin/mail.cgi !!!
2. Copy `src/cgi-bin/mail.cgi` to `/srv/web/ipfire/cgi-bin/mail.cgi`.
3. Copy `src/bin/sendmail.gpg.pl` to `/usr/sbin/sendmail.gpg.pl`.
4. Set permissions: `chown nobody:nobody /srv/web/ipfire/cgi-bin/mail.cgi /usr/sbin/sendmail.gpg.pl && chmod 755 /srv/web/ipfire/cgi-bin/mail.cgi /usr/sbin/sendmail.gpg.pl`.
5. Create GPG directory: `mkdir -p /var/ipfire/dma/encryption && chown nobody:nobody /var/ipfire/dma/encryption && chmod 700 /var/ipfire/dma/encryption`.

## Usage

### Web User Interface (WUI)
- Access: `/cgi-bin/mail.cgi`.
- Configure:
  - **Mail Service**: Enable via "Activate Mail Service" checkbox.
  - **Sender/Recipient**: Set email addresses.
  - **Masquerade Address**: Optional email or hostname (e.g., `your_email@your_provider.com`).
  - **Encryption**: Enable GPG encryption and select a GPG key.
  - **GPG Key Management**: Upload keys, view fingerprints/emails/expiry dates, or delete keys.
  - **Test Mail**: Send unencrypted or encrypted test emails.
- Settings are saved to `/var/ipfire/dma/mail.conf` via the "Save" button.

### Command Line
- Send encrypted emails (requires `ENCRYPT=on` and `GPG_KEY` in `mail.conf`):

```bash
  echo -e "Subject: Log\n\n$(grep error /var/log/messages)" | /usr/sbin/sendmail.gpg recipient@domain.com
```

- Example with custom message:

```bash
echo -e "Subject: Test\n\nHallo verschlüsselte Welt!" | /usr/sbin/sendmail.gpg recipient@domain.com
```

### Configuration File (mail.conf)

Some new fields will be present with the new CGI after importing an OpenPGP key, (currently only RSA no ECC!!!) and after pressing the "Save" button, but it is mostly similar to the original configuration file:
- Path: /var/ipfire/dma/mail.conf .

- Fields:

`USEMAIL`: on or off (enables mail service)
`SENDER`: Sender email (e.g., user@example.com)
`RECIPIENT`: Recipient email (e.g., user@example.com)
`MASQUERADE`: Optional email to override the envelope (e.g., user@example.com)
`ENCRYPT`: on or off (enables GPG encryption)
`GPG_KEY`: GPG key fingerprint (e.g., 0F5C265157C9FDF3C90DA979A881FCB1B0E5161E)

- Settings will be automatically updated via WUI "Save" button.

## Troubleshooting

- WUI errors: `/var/log/httpd/error_log`
- Mail logs: `/var/log/mail`

- **Common Issues**:

- GPG directory missing: Create `/var/ipfire/dma/encryption`
- Missing GnuPG keyring under `/var/ipfire/dma/encryption`
- Invalid GPG key: Verify key fingerprint and recipient match
- Permissions: Ensure `nobody:nobody` ownership and correct permissions

## License

This project is licensed under the [GNU General Public License v3.0](https://www.gnu.org/licenses/gpl-3.0.txt) .

## Author

ummeegge (https://github.com/ummeegge)
Contributions welcome! Open issues or pull requests at https://github.com/ummeegge/IPFire-mail-encryption.

