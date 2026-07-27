import json

import httpx
import respx

from fakturownia_client import Client, FakturowniaClient, Product

CLIENT_JSON = {"id": 5, "name": "ACME", "tax_no": "1234567890", "email": "a@acme.pl"}
PRODUCT_JSON = {"id": 9, "name": "Abonament", "price_net": "89.0", "tax": "23"}


def test_list_clients_filters(api: respx.MockRouter, client: FakturowniaClient) -> None:
    route = api.get("/clients.json").mock(return_value=httpx.Response(200, json=[CLIENT_JSON]))

    clients = client.list_clients(tax_no="1234567890")

    assert isinstance(clients[0], Client)
    assert clients[0].name == "ACME"
    params = dict(httpx.URL(str(route.calls.last.request.url)).params)
    assert params["tax_no"] == "1234567890"
    assert "email" not in params


def test_client_crud_roundtrip(api: respx.MockRouter, client: FakturowniaClient) -> None:
    api.get("/clients/5.json").mock(return_value=httpx.Response(200, json=CLIENT_JSON))
    create = api.post("/clients.json").mock(return_value=httpx.Response(201, json=CLIENT_JSON))
    update = api.put("/clients/5.json").mock(return_value=httpx.Response(200, json=CLIENT_JSON))
    delete = api.delete("/clients/5.json").mock(return_value=httpx.Response(200))

    assert client.get_client(5).id == 5
    client.create_client({"name": "ACME"})
    client.update_client(5, {"email": "new@acme.pl"})
    client.delete_client(5)

    assert json.loads(create.calls.last.request.content) == {"client": {"name": "ACME"}}
    assert json.loads(update.calls.last.request.content) == {"client": {"email": "new@acme.pl"}}
    assert delete.called


def test_product_endpoints(api: respx.MockRouter, client: FakturowniaClient) -> None:
    api.get("/products.json").mock(return_value=httpx.Response(200, json=[PRODUCT_JSON]))
    api.get("/products/9.json").mock(return_value=httpx.Response(200, json=PRODUCT_JSON))
    create = api.post("/products.json").mock(return_value=httpx.Response(201, json=PRODUCT_JSON))
    update = api.put("/products/9.json").mock(return_value=httpx.Response(200, json=PRODUCT_JSON))

    products = client.list_products()
    assert isinstance(products[0], Product)
    assert products[0].price_net == "89.0"
    assert client.get_product(9).name == "Abonament"
    client.create_product({"name": "Abonament", "price_net": "89.0", "tax": "23"})
    client.update_product(9, {"price_net": "99.0"})

    assert set(json.loads(create.calls.last.request.content)) == {"product"}
    assert json.loads(update.calls.last.request.content) == {"product": {"price_net": "99.0"}}
