#!/bin/bash
#
# IPFire Mail Encryption Installer/Uninstaller
#
# This script downloads and installs the IPFire Mail Encryption addon, including
# GPG support for mail.cgi and sendmail.gpg.pl wrapper. It supports uninstall
# with backup/restoration, and update.
#
# Usage:
#   ./install.sh
#   Then follow the interactive menu.
#
# Author: ummeegge
# Date: 2025-09-25
#
# Note: Must be run on an IPFire system.
#

BASE_URL="https://raw.githubusercontent.com/ummeegge/IPFire-mail-encryption/main"
CGI_DIR="/srv/web/ipfire/cgi-bin"
BIN_DIR="/usr/sbin"
GPG_DIR="/var/ipfire/dma/encryption"
BACKUP_FILE="$CGI_DIR/mail.cgi.orig-bck-from-gpg-install"

# Files to download and install
declare -A FILES=(
    ["$CGI_DIR/mail.cgi"]="$BASE_URL/srv_cgi-bin/mail.cgi"
    ["$BIN_DIR/sendmail.gpg.pl"]="$BASE_URL/usr_sbin/sendmail.gpg.pl"
)

# Check if system is IPFire
check_ipfire() {
    if [ -f "$CGI_DIR/mail.cgi" ]; then
        return 0
    else
        echo "Error: $CGI_DIR/mail.cgi not found. This script must be run on an IPFire system."
        exit 1
    fi
}

# Show files with ll or fallback to ls -l
show_files_ll() {
    if command -v ll >/dev/null 2>&1; then
        ll "$@"
    else
        ls -l "$@"
    fi
}

# Install files and set permissions
install_module() {
    echo "Installation started..."

    # Backup existing mail.cgi
    if [ -f "$CGI_DIR/mail.cgi" ]; then
        cp "$CGI_DIR/mail.cgi" "$BACKUP_FILE"
        echo "Backed up $CGI_DIR/mail.cgi to $BACKUP_FILE"
    fi

    # Download and install files
    for file in "${!FILES[@]}"; do
        url="${FILES[$file]}"
        echo "Downloading $url to $file"
        wget -q -O "$file" "$url"
        if [ $? -ne 0 ]; then
            echo "Error downloading $url"
            exit 1
        fi
    done

    # Set permissions
    chmod 755 "$CGI_DIR/mail.cgi" "$BIN_DIR/sendmail.gpg.pl"
    chown root:root "$CGI_DIR/mail.cgi" "$BIN_DIR/sendmail.gpg.pl"

    # Create GPG directory if not exists
    if [ ! -d "$GPG_DIR" ]; then
        mkdir -p "$GPG_DIR"
        chmod 0700 "$GPG_DIR"
        chown nobody:nobody "$GPG_DIR"
        # Initialize GPG-Homedir (empty keyring)
        su nobody -c "gpg --homedir $GPG_DIR --list-keys" 2>/dev/null || true
        # Set permissions for GPG files
        chmod 0640 "$GPG_DIR"/* 2>/dev/null || true
        chown nobody:nobody "$GPG_DIR"/* 2>/dev/null || true
        echo "Created and initialized GPG directory $GPG_DIR"
    else
        echo "GPG directory $GPG_DIR already exists, skipping initialization"
    fi

    # Create symlink for sendmail.gpg if not exists
    if [ ! -L "$BIN_DIR/sendmail.gpg" ]; then
        ln -s "$BIN_DIR/sendmail.gpg.pl" "$BIN_DIR/sendmail.gpg"
        echo "Created symlink $BIN_DIR/sendmail.gpg"
    else
        echo "Symlink $BIN_DIR/sendmail.gpg already exists, skipping"
    fi

    clear
    echo "Installation completed."
    echo ""
    echo "Installed files:"
    show_files_ll "${!FILES[@]}" "$BIN_DIR/sendmail.gpg"
    echo ""
    echo "Next steps:"
    echo "1. Access WUI: /cgi-bin/mail.cgi"
    echo "2. Configure mail settings and import GPG keys"
    echo "3. Press 'Save' to update /var/ipfire/dma/mail.conf"
    echo ""
}

# Uninstall files, restore backup
uninstall_module() {
    echo "Uninstallation started..."

    # Restore mail.cgi from backup
    if [ -f "$BACKUP_FILE" ]; then
        cp "$BACKUP_FILE" "$CGI_DIR/mail.cgi"
        echo "Restored $CGI_DIR/mail.cgi from $BACKUP_FILE"
        rm -f "$BACKUP_FILE"
        echo "Removed backup $BACKUP_FILE"
    else
        echo "No backup found for $CGI_DIR/mail.cgi, removing installed version"
        rm -f "$CGI_DIR/mail.cgi"
    fi

    # Remove sendmail.gpg.pl and symlink
    rm -f "$BIN_DIR/sendmail.gpg.pl" "$BIN_DIR/sendmail.gpg"
    echo "Removed $BIN_DIR/sendmail.gpg.pl and symlink $BIN_DIR/sendmail.gpg"

    # Remove GPG directory if exists
    if [ -d "$GPG_DIR" ]; then
        rm -r "$GPG_DIR"
        echo "Removed GPG directory $GPG_DIR"
    fi

    clear
    echo "Uninstallation completed."
    echo ""
    echo "Restored files:"
    show_files_ll "$CGI_DIR/mail.cgi"
    echo ""
    echo "Next steps:"
    echo "1. Access WUI: /cgi-bin/mail.cgi"
    echo "2. Press 'Save' to update /var/ipfire/dma/mail.conf"
    echo ""
}

# Update by uninstall then install
update_module() {
    echo "Update started..."
    uninstall_module
    install_module
    clear
    echo "Update completed."
    echo ""
    echo "Updated files:"
    show_files_ll "${!FILES[@]}" "$BIN_DIR/sendmail.gpg"
    echo ""
}

# Show interactive menu for user input
show_menu() {
    echo ""
    echo "IPFire Mail Encryption - Choose an option:"
    echo "1) Install"
    echo "2) Uninstall"
    echo "3) Update (Uninstall + Install)"
    echo "4) Exit"
    echo -n "Please enter your choice (1-4): "
}

# Main interactive loop
check_ipfire
while true; do
    show_menu
    read -r choice
    case "$choice" in
        1)
            install_module
            ;;
        2)
            uninstall_module
            ;;
        3)
            update_module
            ;;
        4)
            echo "Exiting."
            exit 0
            ;;
        *)
            echo "Invalid input. Please enter a number from 1 to 4."
            ;;
    esac
done

# EOF
