"""Fake backend of the zebra_day driver: an in-memory ZPL printer.

Gate G7: every public method here is a method of the upstream class ``zebra_day.cmd_mgr:ZebraPrinter``.  The
canned replies follow the upstream simulator's protocol (zebra_day/simulator.py:86-116), but every model name,
serial, counter and configuration string below is test data, marked ``# placeholder``; none is a device fact.
The fake never opens a socket and never talks to a printer.
"""


class FakeZebraPrinter:
    DEFAULT_TIMEOUT = 2.0  # placeholder, copied from the upstream default only to keep the signature

    def __init__(self, ip_address="127.0.0.1", port=9100, buffer_size=4096, **_options):  # placeholder endpoint
        self.ip_address = ip_address
        self.port = port
        self.buffer_size = buffer_size
        self.model = "ZD620-203dpi ZPL"          # placeholder
        self.firmware = "V84.20.21Z"             # placeholder
        self.dpi = "8"                           # placeholder
        self.memory = "8192KB"                   # placeholder
        self.serial = "SIM1001"                  # placeholder
        self.label_count = 12345                 # placeholder
        self.total_inches = 50000                # placeholder
        self.paused = False
        self.paper_out = False
        self.ribbon_out = False
        self.head_up = False
        self._last_configuration = ""            # placeholder: initially no written body
        self.cancelled = False                   # placeholder observer: no sourced cancellation is implemented

    # -- transport ----------------------------------------------------------------------------------------------
    def send_command(self, command, timeout=DEFAULT_TIMEOUT):
        """Answer the fixed ZPL host queries and record a configuration body; unknown commands are ignored."""
        command = command.strip()
        if command == "~HI":
            return f"\x02{self.model},{self.firmware},{self.dpi},{self.memory}\r\n\x03"
        if command == "~HQSN":
            return f"\x02SERIAL NUMBER\r\n{self.serial}\r\n\x03"
        if command == "~HQES":
            return "\x02ERROR STATUS\r\n0000 0000 0000 0000\r\n\x03"    # placeholder flags
        if command == "~HQOD":
            return (f"\x02ODOMETER\r\nLABEL: {self.label_count}\r\n"
                    f"TOTAL INCHES: {self.total_inches}\r\n\x03")
        if command == "~HS":
            pause = "1" if self.paused else "0"
            paper = "1" if self.paper_out else "0"
            head = "1" if self.head_up else "0"
            ribbon = "1" if self.ribbon_out else "0"
            line1 = f"\x020000,0,{pause},0000,000,{paper},{head},{ribbon},000,0,0,0\r\n"  # placeholder frame
            return line1 + "000,0,0,0,0,0,0,0,0000,0\r\n000,0\r\n\x03"  # placeholder frame
        if command == "^XA^HH^XZ":
            return self._configuration_report()
        if command == "^XA^JUS^XZ":
            return None
        if command.startswith("^"):
            # A configuration body sent by set_configuration.  The fake models the write as visible in the next
            # ^HH report; a real printer only shows the settings its report covers.
            self._last_configuration = command
            return None
        return None

    def _configuration_report(self):
        report = (
            "PRINTER CONFIGURATION\r\n"                          # placeholder report
            f"Model: {self.model}\r\n"                          # placeholder
            f"Serial: {self.serial}\r\n"                        # placeholder
            f"Firmware: {self.firmware}\r\n"                    # placeholder
            f"DPI: {self.dpi}\r\n"                              # placeholder
            f"Memory: {self.memory}\r\n"                        # placeholder
            f"Label Count: {self.label_count}\r\n"              # placeholder
        )
        if self._last_configuration:
            report += f"WRITTEN CONFIGURATION: {self._last_configuration}\r\n"
        return report

    # -- upstream query methods ---------------------------------------------------------------------------------
    def get_configuration(self):
        return self.send_command("^XA^HH^XZ", timeout=5.0)       # placeholder: 5.0 is the upstream query timeout

    def set_configuration(self, config):
        self.send_command(config)
        return self.send_command("^XA^JUS^XZ")

    def get_host_identification(self, timeout=DEFAULT_TIMEOUT):
        response = self.send_command("~HI", timeout=timeout)
        if not response:
            return None
        response = response.strip().strip("\x02\x03")
        parts = [part.strip() for part in response.split(",")]
        if len(parts) >= 4:
            return {"model": parts[0], "firmware": parts[1], "dpi": parts[2], "memory": parts[3],
                    "options": parts[4] if len(parts) > 4 else ""}
        return None

    def get_serial_number(self, timeout=DEFAULT_TIMEOUT):
        response = self.send_command("~HQSN", timeout=timeout)
        if not response:
            return None
        response = response.strip().strip("\x02\x03")
        lines = [line.strip() for line in response.replace("\r", "\n").split("\n") if line.strip()]
        for line in lines:
            if "SERIAL" in line.upper():
                continue
            if line:
                return line
        return response if response else None

    def get_error_status(self, timeout=DEFAULT_TIMEOUT):
        response = self.send_command("~HQES", timeout=timeout)
        if not response:
            return None
        response = response.strip().strip("\x02\x03")
        lines = [line.strip() for line in response.replace("\r", "\n").split("\n") if line.strip()]
        flag_line = ""
        for line in lines:
            if "ERROR" in line.upper() or "STATUS" in line.upper():
                continue
            flag_line = line
            break
        return {"errors": [], "warnings": [], "raw": flag_line or response}

    def get_odometer(self, timeout=DEFAULT_TIMEOUT):
        response = self.send_command("~HQOD", timeout=timeout)
        if not response:
            return None
        response = response.strip().strip("\x02\x03")
        result = {"raw": response, "label_count": None, "total_inches": None}
        lines = [line.strip() for line in response.replace("\r", "\n").split("\n") if line.strip()]
        for line in lines:
            if "LABEL" in line.upper() and ":" in line:
                try:
                    result["label_count"] = int(line.split(":")[-1].strip().split()[0].replace(",", ""))
                except (ValueError, IndexError):
                    pass
            elif "INCH" in line.upper() or "TOTAL" in line.upper():
                try:
                    parts = line.split(":")
                    if len(parts) > 1:
                        result["total_inches"] = int(parts[-1].strip().split()[0].replace(",", ""))
                except (ValueError, IndexError):
                    pass
        return result

    def get_host_status(self, timeout=DEFAULT_TIMEOUT):
        response = self.send_command("~HS", timeout=timeout)
        if not response:
            return None
        response = response.strip().strip("\x02\x03")
        result = {"raw": response, "paused": False, "paper_out": False, "ribbon_out": False,
                  "head_up": False, "buffer_full": False}
        lines = [line.strip() for line in response.replace("\r", "\n").split("\n") if line.strip()]
        if lines:
            parts = lines[0].split(",")
            if len(parts) >= 8:
                result["paused"] = parts[2].strip() == "1"
                result["paper_out"] = parts[5].strip() == "1"
                result["head_up"] = parts[6].strip() == "1"
                result["ribbon_out"] = parts[7].strip() == "1"
        return result

    def get_full_status(self, timeout=DEFAULT_TIMEOUT):
        status = {
            "ip": self.ip_address,
            "online": False,
            "host_id": None,
            "serial": None,
            "firmware": None,
            "model": None,
            "dpi": None,
            "error_status": None,
            "odometer": None,
            "host_status": None,
            "errors": [],
            "warnings": [],
            "paused": False,
            "paper_out": False,
            "ribbon_out": False,
            "head_up": False,
            "label_count": None,
            "timestamp": 0.0,                    # placeholder; the driver omits it from state
        }
        host_id = self.get_host_identification(timeout=timeout)
        if host_id:
            status["online"] = True
            status["host_id"] = host_id
            status["model"] = host_id.get("model")
            status["firmware"] = host_id.get("firmware")
            status["dpi"] = host_id.get("dpi")
            serial = self.get_serial_number(timeout=timeout)
            if serial:
                status["serial"] = serial
            error_status = self.get_error_status(timeout=timeout)
            if error_status:
                status["error_status"] = error_status
                status["errors"] = error_status.get("errors", [])
                status["warnings"] = error_status.get("warnings", [])
            odometer = self.get_odometer(timeout=timeout)
            if odometer:
                status["odometer"] = odometer
                status["label_count"] = odometer.get("label_count")
            host_status = self.get_host_status(timeout=timeout)
            if host_status:
                status["host_status"] = host_status
                status["paused"] = host_status.get("paused", False)
                status["paper_out"] = host_status.get("paper_out", False)
                status["ribbon_out"] = host_status.get("ribbon_out", False)
                status["head_up"] = host_status.get("head_up", False)
        return status
