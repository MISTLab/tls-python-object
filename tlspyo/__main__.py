from argparse import ArgumentParser

from tlspyo.credentials import credentials_generator_tool, tcp_broadcast_tls_credentials, tcp_retrieve_tls_credentials, get_default_keys_folder


if __name__ == "__main__":
    parser = ArgumentParser(description='Generate, broadcast or retrieve TLS credentials for tlspyo.')
    parser.add_argument('--credentials', action='store_true', help='generates and displays default credentials folder')
    parser.add_argument('--generate', action='store_true', help='generates credentials')
    parser.add_argument('--custom', action='store_true', help='custom credentials generator')
    parser.add_argument('--retrieve', action='store_true', help='retrieve TLS certificate from server')
    parser.add_argument('--broadcast', action='store_true', help='start credentials server')
    parser.add_argument('--directory', action='store', type=str, default='', help='custom credentials directory')
    parser.add_argument('--ip', action='store', type=str, default='127.0.0.1', help='IP address of the credentials server')
    parser.add_argument('--port', action='store', type=int, default=7776, help='port of the credentials server')
    arguments = parser.parse_args()
    ip = arguments.ip
    port = arguments.port
    directory = arguments.directory
    if directory == '':
        directory = None

    if arguments.credentials:
        folder = get_default_keys_folder
        print(f"tlspyo credentials default directory: {folder}")

    if arguments.retrieve:
        tcp_retrieve_tls_credentials(ip=ip, port=port, directory=directory)
    elif arguments.generate:
        credentials_generator_tool(custom=arguments.custom)

    if arguments.broadcast:  # possible to generate then broadcast
        tcp_broadcast_tls_credentials(port=port, directory=directory)
