#!/usr/bin/env python3
"""Weryfikacja: czy API Fakturowni akceptuje token w naglowku Authorization: Bearer
dla wszystkich endpointow planowanych w fakturownia-client.

Uzycie:
    FAKTUROWNIA_DOMAIN=twojafirma FAKTUROWNIA_API_TOKEN=xxx python3 verify_auth.py

Skrypt NIE tworzy ani nie modyfikuje zadnych danych:
- odczyty: GET z per_page=1
- zapisy: celowo pusty payload -> 422 (walidacja) oznacza, ze autoryzacja przeszla
- PUT/DELETE/change_status: nieistniejace id=0 -> 404 oznacza, ze autoryzacja przeszla
Token nigdy nie jest umieszczany w URL ani wypisywany.
"""

import json
import os
import ssl
import sys
import urllib.error
import urllib.request

DOMAIN = os.environ.get("FAKTUROWNIA_DOMAIN", "").strip()
TOKEN = os.environ.get("FAKTUROWNIA_API_TOKEN", "").strip()

if not DOMAIN or not TOKEN:
    print("Ustaw FAKTUROWNIA_DOMAIN i FAKTUROWNIA_API_TOKEN w srodowisku.")
    sys.exit(2)

DOMAIN = DOMAIN.replace("https://", "").replace("http://", "").split("/")[0]
if not DOMAIN.endswith(".fakturownia.pl"):
    DOMAIN += ".fakturownia.pl"
BASE = f"https://{DOMAIN}"

try:
    import certifi

    CTX = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    CTX = ssl.create_default_context()


def call(method, path, *, body=None, auth=True):
    url = BASE + path
    headers = {"Accept": "application/json"}
    if auth:
        headers["Authorization"] = f"Bearer {TOKEN}"
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30, context=CTX) as resp:
            return resp.status, resp.read()[:200]
    except urllib.error.HTTPError as e:
        return e.code, e.read()[:200]
    except Exception as e:  # noqa: BLE001
        return None, str(e).encode()[:200]


def snippet(raw):
    text = raw.decode("utf-8", "replace").replace("\n", " ")
    if TOKEN in text:
        text = text.replace(TOKEN, "***TOKEN***")
    return text[:110]


results = []


def check(name, method, path, *, body=None, ok_statuses, auth=True, note=""):
    status, raw = call(method, path, body=body, auth=auth)
    passed = status in ok_statuses
    results.append((name, f"{method} {path}", status, passed, note, snippet(raw)))
    return status, raw


# --- kontrola negatywna: bez tokenu musi byc 401 ---
check(
    "kontrola negatywna (bez tokenu)",
    "GET",
    "/invoices.json?per_page=1&page=1",
    ok_statuses={401},
    auth=False,
    note="oczekiwane 401",
)

# --- odczyty ---
status, raw = check("list invoices", "GET", "/invoices.json?per_page=1&page=1", ok_statuses={200})
invoice_id = None
if status == 200:
    # call() obcina body do 200 B; pobierz pelna odpowiedz raz jeszcze recznie
    req = urllib.request.Request(
        BASE + "/invoices.json?per_page=1&page=1",
        headers={"Authorization": f"Bearer {TOKEN}", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30, context=CTX) as resp:
            items = json.loads(resp.read())
            if items:
                invoice_id = items[0].get("id")
    except Exception:  # noqa: BLE001
        pass

check("list clients", "GET", "/clients.json?per_page=1&page=1", ok_statuses={200})
check("list products", "GET", "/products.json?per_page=1&page=1", ok_statuses={200})

if invoice_id:
    check("get invoice", "GET", f"/invoices/{invoice_id}.json", ok_statuses={200})
    check("get invoice PDF", "GET", f"/invoices/{invoice_id}.pdf", ok_statuses={200})
else:
    print("(brak faktur na koncie - pomijam get invoice / PDF)")

# --- zapisy bez tworzenia danych: pusty payload -> 422 = auth przeszla ---
check(
    "create invoice (auth only)",
    "POST",
    "/invoices.json",
    body={"invoice": {}},
    ok_statuses={422, 400},
    note="422/400 = auth OK, walidacja odrzucila pusty payload",
)
check(
    "create client (auth only)",
    "POST",
    "/clients.json",
    body={"client": {}},
    ok_statuses={422, 400},
    note="422/400 = auth OK",
)
check(
    "create product (auth only)",
    "POST",
    "/products.json",
    body={"product": {}},
    ok_statuses={422, 400},
    note="422/400 = auth OK",
)

# --- PUT/DELETE/change_status na nieistniejacym id=0 -> 404 = auth przeszla ---
check(
    "update invoice (auth only)",
    "PUT",
    "/invoices/0.json",
    body={"invoice": {}},
    ok_statuses={404},
    note="404 = auth OK (id=0 nie istnieje)",
)
check(
    "change invoice status (auth only)",
    "POST",
    "/invoices/0/change_status.json?status=paid",
    ok_statuses={404},
    note="404 = auth OK",
)
check(
    "update client (auth only)",
    "PUT",
    "/clients/0.json",
    body={"client": {}},
    ok_statuses={404},
    note="404 = auth OK",
)
check(
    "delete client (auth only)",
    "DELETE",
    "/clients/0.json",
    ok_statuses={404},
    note="404 = auth OK",
)
check(
    "update product (auth only)",
    "PUT",
    "/products/0.json",
    body={"product": {}},
    ok_statuses={404},
    note="404 = auth OK",
)
check(
    "delete invoice (auth only)",
    "DELETE",
    "/invoices/0.json",
    ok_statuses={404},
    note="404 = auth OK",
)
check(
    "delete product (endpoint nieudok.)",
    "DELETE",
    "/products/0.json",
    ok_statuses={404},
    note="404 moze oznaczac brak route LUB brak rekordu - wynik orientacyjny",
)

# --- raport ---
print(f"\nBaza: {BASE}  (token: ***ukryty***)\n")
w = max(len(r[0]) for r in results)
all_ok = True
for name, endpoint, status, passed, note, body in results:
    mark = "OK " if passed else "FAIL"
    if not passed:
        all_ok = False
    print(f"[{mark}] {name.ljust(w)}  {endpoint}")
    print(f"       -> HTTP {status}  {note}")
    print(f"       -> body: {body}")

print()
if all_ok:
    print("WNIOSEK: Plan A - wszystkie endpointy akceptuja Authorization: Bearer.")
else:
    print("WNIOSEK: sa odstepstwa - patrz FAIL wyzej (mozliwy Plan B).")
sys.exit(0 if all_ok else 1)
