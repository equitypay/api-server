from server.sync import sync_peers
import json

if __name__ == "__main__":
    # sync_peers()
    with open("check.json") as file:
        data = json.load(file)

        ips = [entry["address"] for entry in data["result"]]

        print(len(ips))

        ips = list(set(ips))

        print(len(ips))
