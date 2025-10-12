import os
import requests

def create_proxy_list():

    TOKEN = os.getenv("PROXY_TOKEN")

    response = requests.get(
        "https://proxy.webshare.io/api/v2/proxy/config/",
        headers={"Authorization": f"Token {TOKEN}"}
    )

    DOWNLOAD_TOKEN = response.json()["proxy_list_download_token"]

    response = requests.get(
        f"https://proxy.webshare.io/api/v2/proxy/list/download/{DOWNLOAD_TOKEN}/-/any/username/direct/-/"
    )
    
    proxies = response.text.strip().split("\r\n")
    proxies = [
        f"http://{user}:{pwd}@{ip}:{port}"
        for ip, port, user, pwd in (proxy.split(":") for proxy in proxies)
    ]

    with open("proxy_list.txt", "w") as f:
        for proxy in proxies:
                f.write(proxy + "\n")