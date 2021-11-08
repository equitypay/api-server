# Getting started

API for interaction with EquityPay blockchain.

# How to use it?

First of all you have to create `config.py` file in root of project directory with following content:

```
rid = "api-server"
cache = 3600  # Cache request for 1 hour
secret = 'YOU SHOULD HAVE A VERY STRONG PASSWORD HERE'
endpoint = "http://rpcuser:rpcpassword@127.0.0.1:9999/"
host = "0.0.0.0"
port = 1234
debug = False
```

# Install dependencies
```
$ sudo apt-get install python3-pip
$ pip3 install -r requirements.txt
```

# Run
```
$ python3 app.py
```

All request should be send to this endpoint: `https://api.equitypay.com`

Responce have following fields:

- `result`: list or object which contains requested data.
- `error`: this field contains error message in case something went wrong.
- `id`: api server identifier which is set in `config.py` file.

P.s. keep in mind, that all amounts in this API should be in **Satoshis**.

# Nginx

```
server {
    listen 80;
    server_name domain.com;

    location / {
        proxy_pass http://localhost:4321;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }
}
```