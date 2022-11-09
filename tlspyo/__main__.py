from argparse import ArgumentParser

from tlspyo.credentials import credentials_generator_tool


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument('--credentials', action='store_true', help='generates credentials')
    parser.add_argument('--custom', action='store_true', help='customize credentials')
    arguments = parser.parse_args()

    if arguments.credentials:
        credentials_generator_tool(custom=arguments.custom)
