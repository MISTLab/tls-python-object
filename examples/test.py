from argparse import ArgumentParser
import time
import random

from tlspyo import Relay, Endpoint


if __name__ == '__main__':

    parser = ArgumentParser()
    parser.add_argument('--endpoint', dest='endpoint', action='store_true', default=False, help='Start as endpoint.')
    parser.add_argument('--relay', dest='relay', action='store_true', default=True, help='Start as relay.')
    parser.add_argument('--password', dest='password', type=str, default="pswd", help='Server password.')
    parser.add_argument('--port', dest='port', type=int, default=2098, help='Server port.')
    parser.add_argument('--ip', dest='ip', default="127.0.0.1", type=str, help='Server IP.')
    parser.add_argument('--local_port', dest='local_port', type=int, default=3000, help='Local port.')

    args = parser.parse_args()

    if args.endpoint:
        group = str(args.local_port)
        ep = Endpoint(ip_server=args.ip,
                      port_server=args.port,
                      password=args.password,
                      groups=group,
                      local_com_port=args.local_port)
        cpt = 1
        while True:
            obj_s = 'salut' + str(cpt) + 'from' + group
            cpt += 1
            dest_s = "3001" if args.local_port == 3000 else "3000"
            # ep.send_object(obj_s, destination=dest_s)
            ep.produce(obj=obj_s, group=dest_s)

            time.sleep(random.uniform(0, 10))
            if args.local_port == 3000:
                ep.notify(origins={group: 2})
                print(f"{group} received: {ep.pop(max_items=2, blocking=True)}")
            else:
                ep.notify(origins={group: -1})
                print(f"{group} received: {ep.receive_all(blocking=False)}")
            # time.sleep(2)

    else:
        re = Relay(port=args.port,
                   password=args.password,
                   accepted_groups=None)
        while True:
            time.sleep(1)
