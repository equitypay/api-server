from server import utils


class General:
    @classmethod
    def info(cls):
        data = utils.make_request("getblockchaininfo")

        if data["error"] is None:
            data["result"]["supply"] = utils.supply(data["result"]["blocks"])[
                "supply"
            ]
            data["result"]["reward"] = utils.reward(data["result"]["blocks"])
            data["result"].pop("verificationprogress")
            data["result"].pop("initialblockdownload")
            data["result"].pop("pruned")
            data["result"].pop("warnings")
            data["result"].pop("size_on_disk")

            nethash = utils.make_request(
                "getnetworkhashps", [120, data["result"]["blocks"]]
            )
            if nethash["error"] is None:
                data["result"]["nethash"] = int(nethash["result"])

        return data

    @classmethod
    def supply(cls):
        data = utils.make_request("getblockchaininfo")

        if data["error"] is None:
            height = data["result"]["blocks"]
            result = utils.supply(height)
            result["height"] = height

        else:
            result = utils.supply(0)
            result["height"] = 0

        return result

    @classmethod
    def fee(cls):
        return utils.response({"feerate": utils.satoshis(0.03), "blocks": 6})

    @classmethod
    def mempool(cls):
        data = utils.make_request("getmempoolinfo")

        if data["error"] is None:
            if data["result"]["size"] > 0:
                mempool = utils.make_request("getrawmempool")["result"]
                data["result"]["tx"] = mempool
            else:
                data["result"]["tx"] = []

        return data

    @classmethod
    def current_height(cls):
        data = utils.make_request("getblockcount")
        height = 0

        if data["error"] is None:
            height = data["result"]

        return height

    @classmethod
    def mininginfo(cls):
        data = utils.make_request("getmininginfo")
        result = 0

        if data["error"] is None:
            result = data["result"]

        return result
