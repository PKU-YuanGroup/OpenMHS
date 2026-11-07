"""Hardware transport factory for the APO dome Alpaca server (reviewed hardware backend only).

The acceptance gate never imports this module. The TagDriver refuses the
hardware backend until a human signs ``reviewed_by`` with scope ``hardware`` in
driver.lock.json, at every risk class and for every author. ``connect`` builds
an HTTP client for the Alpaca server started by ``device/dome_app.py``; it does
not import or execute the upstream device code. The server host and port are
operator deployment options, not facts of the clone (the sample config.toml
sets port 5555, but a deployed server can use another address).

The transport implements the TagBridge Alpaca interface:

* ``read_point`` sends GET /api/v1/<device_type>/<device_number>/<member> and
  returns the parsed ASCOM response object, whose ``Value`` the bridge decodes;
* ``write_point`` sends PUT with the point's ``field`` form value;
* ``invoke_point`` sends PUT with the method's declared form fields.

``ClientID`` and ``ClientTransactionID`` accompany every request, as the ASCOM
Alpaca protocol requires. The parsed response is returned even when it carries
an Alpaca error: the bridge classifies the numbers that mean "not performed"
and treats every other number as an unknown outcome. A transport failure (a
connection error, a non-JSON body, an HTTP status without an Alpaca response)
raises, so the bridge records an unknown outcome rather than a refusal.

The reviewer must, before signing: confirm the deployed host, port and device
number, run this against the server under supervision, and verify how the
server reports a lost response, how long a worker thread takes to switch the
rotation relay on after SlewToAzimuth, Park and FindHome (the package waits at
most ``confirm_ms``), and that the single-threaded server still answers
``AbortSlew`` while a request waits on the weather check. The stop is not
independent relay feedback; the dome's power switch is the real stop.
"""

import json
import urllib.error
import urllib.parse
import urllib.request

CLIENT_ID = "openmhs:holtzmanjon:apoalpyca"


def connect(host, port, device_number=0, client_id=CLIENT_ID, **_options):
    """Build an Alpaca HTTP transport for the operator's server (host and port are required)."""
    return AlpacaHttpTransport(str(host), int(port), int(device_number), str(client_id))


class AlpacaHttpTransport:
    """One Alpaca server: stateless HTTP requests with the caller's timeout on each request."""

    def __init__(self, host, port, device_number, client_id):
        self._base = f"http://{host}:{port}"
        self._device_number = device_number
        self._client_id = client_id
        self._transaction = 0

    def _request(self, method, device_type, number, member, form, timeout_s):
        self._transaction += 1
        query = {"ClientID": self._client_id, "ClientTransactionID": self._transaction}
        query.update({key: str(value) for key, value in (form or {}).items()})
        url = (f"{self._base}/api/v1/{urllib.parse.quote(str(device_type), safe='')}/"
               f"{int(number)}/{urllib.parse.quote(str(member), safe='')}")
        if method == "GET":
            request = urllib.request.Request(url + "?" + urllib.parse.urlencode(query), method="GET")
        else:
            request = urllib.request.Request(url, data=urllib.parse.urlencode(query).encode("utf-8"),
                                             method="PUT",
                                             headers={"Content-Type": "application/x-www-form-urlencoded"})
        try:
            with urllib.request.urlopen(request, timeout=float(timeout_s)) as response:
                body = response.read()
        except urllib.error.HTTPError as exc:
            body = exc.read()
            if not body:
                raise
        try:
            decoded = json.loads(body.decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as exc:
            raise RuntimeError("the Alpaca server did not return a JSON response") from exc
        if type(decoded) is not dict or "ErrorNumber" not in decoded:
            raise RuntimeError("the Alpaca server response is not an ASCOM response object")
        return decoded

    def read_point(self, request, *, timeout_s):
        return self._request("GET", request["device_type"], request["device_number"], request["member"],
                             None, timeout_s)

    def write_point(self, request, raw, *, timeout_s):
        if "field" not in request:
            raise ValueError("a writable Alpaca point needs a PUT form field")
        return self._request("PUT", request["device_type"], request["device_number"], request["member"],
                             {request["field"]: raw}, timeout_s)

    def invoke_point(self, request, args, *, timeout_s):
        return self._request("PUT", request["device_type"], request["device_number"], request["member"],
                             dict(args), timeout_s)

    def close(self):
        """No persistent connection is kept."""
