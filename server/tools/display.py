from .. import utils

# ToDo: Get rid of all this

def tx_to_db(data):
    result = data["result"]

    output_amount = 0
    input_amount = 0
    outputs = []
    inputs = []

    for vin in data["result"]["vin"]:
        if "coinbase" in vin:
            continue

        amount = utils.amount(vin["value"])
        address = vin["scriptPubKey"]["addresses"][0]

        inputs.append({
            "address": address,
            "amount": amount
        })

        input_amount += amount

    for vout in data["result"]["vout"]:
        if vout["scriptPubKey"]["type"] in ["nonstandard", "nulldata"]:
            continue

        category = vout["scriptPubKey"]["type"]
        amount = utils.amount(vout["value"])
        address = vout["scriptPubKey"]["addresses"][0]

        outputs.append({
            "address": address,
            "amount": amount,
            "category": category,
            "spent": False
        })

        output_amount += amount

    confirmations = result["confirmations"] if "confirmations" in result else 0

    return {
        "confirmations": confirmations,
        "fee": float(input_amount - output_amount),
        "timestamp": result["timestamp"],
        "amount": utils.amount(result["amount"]),
        "coinstake": False,
        "height": data["result"]["height"],
        "coinbase": False,
        "txid": result["txid"],
        "size": result["size"],
        "outputs": outputs,
        "mempool": True if result["height"] < 0 else False,
        "inputs": inputs
    }

def tx_to_wallet(data):
    result = data["result"]

    output_amount = 0
    input_amount = 0
    outputs = []
    inputs = []

    for vin in data["result"]["vin"]:
        if "coinbase" in vin:
            continue

        amount = vin["value"]
        address = vin["scriptPubKey"]["addresses"][0]

        inputs.append({
            "address": address,
            "amount": amount,
        })

        input_amount += amount

    for vout in data["result"]["vout"]:
        if vout["scriptPubKey"]["type"] in ["nonstandard", "nulldata"]:
            continue

        category = vout["scriptPubKey"]["type"]
        amount = vout["value"]
        address = vout["scriptPubKey"]["addresses"][0]

        outputs.append({
            "address": address,
            "amount": amount,
            "category": category,
            "spent": False
        })

        output_amount += amount

    confirmations = result["confirmations"] if "confirmations" in result else 0

    return {
        "confirmations": confirmations,
        "fee": float(input_amount - output_amount),
        "timestamp": result["timestamp"],
        "amount": result["amount"],
        "coinstake": False,
        "height": data["result"]["height"],
        "coinbase": False,
        "txid": result["txid"],
        "size": result["size"],
        "outputs": outputs,
        "mempool": True if result["height"] < 0 else False,
        "inputs": inputs
    }
