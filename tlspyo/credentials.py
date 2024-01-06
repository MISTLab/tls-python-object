from pathlib import Path
import datetime
import socket

from platformdirs import user_data_dir
from OpenSSL import crypto


__docformat__ = "google"


DEFAULT_KEYS_FOLDER = Path(user_data_dir()) / "tlspyo" / "credentials"


def get_default_keys_folder():
    """
    Creates the default credentials directory and returns it.

    Returns:
        pathlib.Path: default credentials directory
    """
    if not DEFAULT_KEYS_FOLDER.exists():
        DEFAULT_KEYS_FOLDER.mkdir(parents=True, exist_ok=True)
    return DEFAULT_KEYS_FOLDER


def generate_tls_credentials(
        folder_path,
        email_address="emailAddress",
        common_name="default",
        subject_alt_name=('DNS:default',),
        country_name="CA",
        locality_name="localityName",
        state_or_province_name="stateOrProvinceName",
        organization_name="organizationName",
        organization_unit_name="organizationUnitName",
        serial_number=0,
        validity_end_in_seconds=10*365*24*60*60):
    """
    Generates a private TLS key and a self-signed TLS certificate in the designed folder.

    Args:
        folder_path (path-like object): path were the files will be created
        email_address (str): your email address
        common_name (str): your hostname
        subject_alt_name (tuple of str): your subject alt name list
        country_name (str): your country code
        locality_name (str): your locality name
        state_or_province_name (str): your state name
        organization_name (str): your organization name
        organization_unit_name (str): your organization unit name
        serial_number (int): the serial number of your certificate
        validity_end_in_seconds (int): seconds until the generated certificate will expire
    """

    key_file = Path(folder_path) / "key.pem"
    cert_file = Path(folder_path) / "certificate.pem"

    k = crypto.PKey()
    k.generate_key(crypto.TYPE_RSA, 4096)
    cert = crypto.X509()

    subject = cert.get_subject()
    subject.commonName = common_name
    subject.emailAddress = email_address
    subject.organizationName = organization_name
    subject.organizationalUnitName = organization_unit_name
    subject.localityName = locality_name
    subject.stateOrProvinceName = state_or_province_name
    subject.countryName = country_name

    cert.set_issuer(subject)
    cert.gmtime_adj_notBefore(0)
    cert.gmtime_adj_notAfter(validity_end_in_seconds)
    cert.set_pubkey(k)
    cert.set_serial_number(serial_number)
    cert.set_version(2)  # for SAN
    cert.add_extensions([
        crypto.X509Extension(b'subjectAltName', False, ','.join(subject_alt_name).encode())
    ])

    cert.sign(k, 'sha512')
    with open(cert_file, "wt") as f:
        f.write(crypto.dump_certificate(crypto.FILETYPE_PEM, cert).decode("utf-8"))
    with open(key_file, "wt") as f:
        f.write(crypto.dump_privatekey(crypto.FILETYPE_PEM, k).decode("utf-8"))


def credentials_generator_tool(custom=False):
    """
    Helper tool to generate credentials via CLI.

    Args:
        custom (bool): whether to customize the certificate
    """

    folder_path = get_default_keys_folder()
    email_address = "emailAddress"
    common_name = "default"
    subject_alt_name = ["DNS:" + common_name]
    country_name = "CA"
    locality_name = "localityName"
    state_or_province_name = "stateOrProvinceName"
    organization_name = "organizationName"
    organization_unit_name = "organizationUnitName"
    serial_number = 0
    validity_end_in_seconds = 10 * 365 * 24 * 60 * 60

    if custom:

        print(f"=== TLSPYO - TLS credentials generation tool ===")
        print(f"Please fill the following fields (press ENTER fo leave the default as displayed between brackets)")

        print(f"\nCredentials folder [{folder_path}]:")
        inp = input()
        if inp != "":
            folder_path = Path(inp)
        print(folder_path)

        print(f"\nEmail address [{email_address}]:")
        inp = input()
        if inp != "":
            email_address = inp
        print(email_address)

        print(f"\nCommon name (hostname) [{common_name}]:")
        inp = input()
        if inp != "":
            common_name = inp
        print(common_name)

        subject_alt_name = ["DNS:" + common_name]
        print(f"\nSubject alternative name (hostnames, leave empty to stop adding) {subject_alt_name}:")
        inp = input()
        if inp != "":
            subject_alt_name = []
            while inp != "":
                subject_alt_name.append(inp)
                inp = input()
        print(subject_alt_name)

        print(f"\nCountry code [{country_name}]:")
        inp = input()
        if inp != "":
            country_name = inp
        print(country_name)

        print(f"\nLocality name [{locality_name}]:")
        inp = input()
        if inp != "":
            locality_name = inp
        print(locality_name)

        print(f"\nState or province [{state_or_province_name}]:")
        inp = input()
        if inp != "":
            state_or_province_name = inp
        print(state_or_province_name)

        print(f"\nOrganization name [{organization_name}]:")
        inp = input()
        if inp != "":
            organization_name = inp
        print(organization_name)

        print(f"\nOrganization unit [{organization_unit_name}]:")
        inp = input()
        if inp != "":
            organization_unit_name = inp
        print(organization_unit_name)

        print(f"\nCertificate serial number [{serial_number}]:")
        inp = input()
        if inp != "":
            serial_number = inp
        print(serial_number)

        print(f"\nCertificate validity (in seconds) [{validity_end_in_seconds}]:")
        inp = input()
        if inp != "":
            validity_end_in_seconds = int(inp)
        print(datetime.timedelta(seconds=validity_end_in_seconds))

    generate_tls_credentials(folder_path=folder_path,
                             email_address=email_address,
                             common_name=common_name,
                             subject_alt_name=tuple(subject_alt_name),
                             country_name=country_name,
                             locality_name=locality_name,
                             state_or_province_name=state_or_province_name,
                             organization_name=organization_name,
                             organization_unit_name=organization_unit_name,
                             serial_number=serial_number,
                             validity_end_in_seconds=validity_end_in_seconds)

    print(f"Credentials successfully generated in {folder_path}")


def tcp_broadcast_tls_credentials(port, directory=None):
    """
    Starts a server that broadcasts certificate.pem over TCP.

    Args:
        port: port
        directory: directory where to find certificate.pem if not the default credential directory
    """
    folder = get_default_keys_folder() if directory is None else directory
    cert_path = folder / 'certificate.pem'
    if not cert_path.exists():
        print(f"certificate.pem file not found in {folder}, please generate it first.")
        print("You can generate a certificate.pem in the default tlspyo directory with the following command:")
        print("python -m tlspyo --generate")
        return
    else:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as com_srv:
            com_srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            com_srv.bind(('', port))
            com_srv.listen()
            print("Starting credentials server, close the terminal to exit.")
            while True:
                try:
                    conn, addr = com_srv.accept()
                    with conn:
                        with open(cert_path, 'rb') as f:
                            conn.sendfile(f)
                        print(f"Sent TLS certificate to {addr} via port {port}.")
                    print(f"Connection closed.")
                except KeyboardInterrupt:
                    break


def tcp_retrieve_tls_credentials(ip, port, directory=None):
    """
    Starts a client that retrieves certificate.pem over TCP.

    The credential-broadcasting server must be launched via tcp_broadcast_tls_credentials on the Relay machine.

    Args:
        ip: ip of the credential-broadcasting server
        port: port of the credential-broadcasting server
        directory: directory where to write certificate.pem if not the default credentials directory
    """
    folder = get_default_keys_folder() if directory is None else directory
    cert_path = folder / 'certificate.pem'
    print(f"Attempting to reach credentials server at address {ip}:{port}")
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((ip, port))
        while True:
            data = s.recv(1024)
            if not data:
                break
    with open(cert_path, 'wb') as f:
        f.write(data)
    print(f"TLS certificate correctly received in {cert_path}")
