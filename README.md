# IPFire Mail Encryption Addon

This addon enhances IPFire's `mail.cgi` with GPG encryption and masquerade support, enabling secure email delivery for logs, alerts, and test mails via the Web User Interface (WUI) or command line.

## Features

- **GPG Key Management**: Upload, view, and delete GPG keys in the WUI, currently only RSA, ECC is not supported with `gpg (GnuPG) 1.4.23`
- **GPG Encryption**: Send encrypted emails using GPG keys via command line or scripts, configured via WUI.
- **Masquerade Option**: Set an alternative sender address (email or hostname) for outgoing emails.
- **Test Mail**: Send unencrypted or encrypted test emails from the WUI.
- **Command-Line Support**: Pipe logs or messages to `/usr/sbin/sendmail.gpg` for encrypted delivery.
- **Debugging**: Detailed logs in `/var/log/httpd/error_log` and `/var/log/mail`.

## Prerequisites

- IPFire with Core version >= 94
- GPG (`/usr/bin/gpg`), `MIME::Lite`, and `sendmail.dma` are part of the core system and should be installed
- GPG key directory: `/var/ipfire/dma/encryption` (must exist)
- GPG keyring: Installed under `/var/ipfire/dma/encryption`

## Installation

Manual installation:
1. Most important, make a Backup of the existing /srv/web/ipfire/cgi-bin/mail.cgi !!!
2. Copy `src/cgi-bin/mail.cgi` to `/srv/web/ipfire/cgi-bin/mail.cgi`.
3. Copy `src/bin/sendmail.gpg.pl` to `/usr/sbin/sendmail.gpg.pl`.
4. Set permissions: `chown nobody:nobody /srv/web/ipfire/cgi-bin/mail.cgi /usr/sbin/sendmail.gpg.pl && chmod 755 /srv/web/ipfire/cgi-bin/mail.cgi /usr/sbin/sendmail.gpg.pl`.
5. Create GPG directory: `mkdir -p /var/ipfire/dma/encryption && chown nobody:nobody /var/ipfire/dma/encryption && chmod 700 /var/ipfire/dma/encryption`.

an [in- uninstaller / updater](https://github.com/ummeegge/IPFire-mail-encryption/blob/main/installer.sh) is meanwhile available.

## Usage

### Web User Interface (WUI)
- Access: `/cgi-bin/mail.cgi`.
- Configure:
  - **Mail Service**: Enable via "Activate Mail Service" checkbox.
  - **Sender/Recipient**: Set email addresses.
  - **Masquerade Address**: Optional email or hostname (e.g., `your_email@your_provider.com`).
  - **Encryption**: Enable GPG encryption via `Encrypt Mail GPG Key` and press `save` and select and upload an GPG key.
  - **GPG Key Management**: Upload keys, view fingerprints/emails/expiry dates, or delete keys.
  - **Test Mail**: Send unencrypted or encrypted test emails.
  - Settings are saved to `/var/ipfire/dma/mail.conf` via the "Save" button.

### Command Line
- Send encrypted emails (requires `ENCRYPT=on` and `GPG_KEY` in `mail.conf`):

```bash
echo -e "Subject: Error Logs\n\n$(grep error /var/log/messages)" | /usr/sbin/sendmail.gpg recipient@domain.com
```

- Example with custom message:

```bash
echo -e "Subject: Test\n\nHello encrypted World!" | /usr/sbin/sendmail.gpg recipient@domain.com
```

### Configuration File (mail.conf)

Some new fields will be present with the new CGI after importing an OpenPGP key, (currently only RSA no ECC!!!) and after pressing the "Save" button, but it is mostly similar to the original configuration file:
- Path: /var/ipfire/dma/mail.conf .

- Fields:

```
`USEMAIL`: on or off (enables mail service)
`SENDER`: Sender email (e.g., user@example.com)
`RECIPIENT`: Recipient email (e.g., user@example.com)
`MASQUERADE`: Optional email to override the envelope (e.g., user@example.com)
`ENCRYPT`: on or off (enables GPG encryption)
`GPG_KEY`: GPG key fingerprint (e.g., 0F5C265157C9FDF3C90DA979A881FCB1B0E5161E)
```

- Settings will be automatically updated via WUI "Save" button.

## Troubleshooting

- WUI errors: `/var/log/httpd/error_log`
- Mail logs: `/var/log/mail`

- **Common Issues**:

- GPG directory missing: Create `/var/ipfire/dma/encryption`
- Missing GnuPG keyring under `/var/ipfire/dma/encryption`
- Invalid GPG key: Verify key fingerprint and recipient match
- Permissions: Ensure `nobody:nobody` ownership and correct permissions
- After in- or uninstallation, use always the Web UIs `Save` button to restore the appropriate settings
- By in or uninstalling the new CGI, it is a know issue that the `Mail Password` needs to be re-entered

## License

This project is licensed under the [GNU General Public License v3.0](https://www.gnu.org/licenses/gpl-3.0.txt) .

## Author

ummeegge (https://github.com/ummeegge)
Contributions welcome! Open issues or pull requests at https://github.com/ummeegge/IPFire-mail-encryption.

