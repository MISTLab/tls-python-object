from pathlib import Path
import datetime

from OpenSSL import crypto


DEFAULT_KEYS_FOLDER = Path.home() / "tlspyo" / "credentials"


def generate_tls_credentials(
        folder_path,
        email_address="emailAddress",
        common_name="default",
        country_name="CA",
        locality_name="localityName",
        state_or_province_name="stateOrProvinceName",
        organization_name="organizationName",
        organization_unit_name="organizationUnitName",
        serial_number=0,
        validity_end_in_seconds=10*365*24*60*60):
    """
    Generates a private TLS key and a self-signed TLS certificate in the designed folder.

    :param folder_path: path-like object: path were the files will be created
    :param email_address: str: your email address
    :param common_name: str: your hostname
    :param country_name: str your country code
    :param locality_name: str: your locality name
    :param state_or_province_name: str: your state name
    :param organization_name: str: your organization name
    :param organization_unit_name: str: your organization unit name
    :param serial_number: int: the serial number of your certificate
    :param validity_end_in_seconds: int: seconds until the generated certificate will expire
    """

    key_file = Path(folder_path) / "key.pem"
    cert_file = Path(folder_path) / "certificate.pem"

    k = crypto.PKey()
    k.generate_key(crypto.TYPE_RSA, 4096)
    cert = crypto.X509()
    cert.get_subject().C = country_name
    cert.get_subject().ST = state_or_province_name
    cert.get_subject().L = locality_name
    cert.get_subject().O = organization_name
    cert.get_subject().OU = organization_unit_name
    cert.get_subject().CN = common_name
    cert.get_subject().emailAddress = email_address
    cert.set_serial_number(serial_number)
    cert.gmtime_adj_notBefore(0)
    cert.gmtime_adj_notAfter(validity_end_in_seconds)
    cert.set_issuer(cert.get_subject())
    cert.set_pubkey(k)
    cert.sign(k, 'sha512')
    with open(cert_file, "wt") as f:
        f.write(crypto.dump_certificate(crypto.FILETYPE_PEM, cert).decode("utf-8"))
    with open(key_file, "wt") as f:
        f.write(crypto.dump_privatekey(crypto.FILETYPE_PEM, k).decode("utf-8"))


def credentials_generator_tool(custom=False):

    folder_path = DEFAULT_KEYS_FOLDER
    email_address = "emailAddress"
    common_name = "default"
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
                             country_name=country_name,
                             locality_name=locality_name,
                             state_or_province_name=state_or_province_name,
                             organization_name=organization_name,
                             organization_unit_name=organization_unit_name,
                             serial_number=serial_number,
                             validity_end_in_seconds=validity_end_in_seconds)

    print(f"Credentials successfully generated in {folder_path}")
