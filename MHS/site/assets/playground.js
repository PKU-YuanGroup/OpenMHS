/* OpenMHS playground — an in-browser reference model of one OpenMHS endpoint.
   It implements the subset of wire revision 1 the page documents. It is NOT a device,
   it talks to nothing, and it is not the evidence chain of any real endpoint. */
(function () {
  "use strict";
  var editor = document.getElementById("request-editor");
  if (!editor) return;
  var sendBtn = document.getElementById("send-request");
  var formatBtn = document.getElementById("format-json");
  var resetBtn = document.getElementById("reset-request");
  var errorEl = document.getElementById("request-error");
  var respStatus = document.getElementById("response-status");
  var respJson = document.getElementById("response-json");
  var receiptCard = document.getElementById("receipt-card");
  var logEl = document.getElementById("event-log");
  var counter = 0;
  var model = freshModel();
  var HELLO = {
    server: { name: "mhs-playground", version: "1.0.0" },
    mhs_version: "1.0",
    protocol_versions: ["1.0"],
    endpoint_id: "mhs://playground/conveyor",
    features: ["MHS.SAFETY.NOT_CERTIFIED", "playground-reference-model", "deterministic-integer-simulation"],
    limits: { max_batch: 1, max_command_deadline_ms: 60000 },
    conformance: { profile: "MHS-Sim", level: "CL0", issuer_kind: "self",
      report_digest: null, note: "Reference model only; no conformance report." },
    devices: [deviceSummary()],
    safety: { certified: false, notice: "MHS.SAFETY.NOT_CERTIFIED" }
  };

  function freshModel() {
    return {
      endpointId: "mhs://playground/conveyor",
      deviceId: "mhs://playground/conveyor/lab/conveyor-workcell",
      instanceId: "01J8ZQ3V6Y7M2N4P6R8S0T2V4W",
      mode: "simulated",
      revision: 7,
      tick: 0,
      door: "closed",
      estop: "released",
      latched: false,
      gate: "main",
      drive: "running",
      velocity: 120,
      parts: [{ id: "part-1", position: 0, route: "main" }],
      partSeq: 1,
      delivered: 0,
      commandIds: {},
      receipts: [],
      seq: 0,
      sessionSeq: 0,
      genesisDigest: digest({ kind: "genesis", endpoint_id: "mhs://playground/conveyor", mhs_version: "1.0", seq: 0 })
    };
  }
  function canonical(value) {
    if (Array.isArray(value)) return "[" + value.map(canonical).join(",") + "]";
    if (value && typeof value === "object") {
      return "{" + Object.keys(value).sort().map(function (key) {
        return JSON.stringify(key) + ":" + canonical(value[key]);
      }).join(",") + "}";
    }
    return JSON.stringify(value === undefined ? null : value);
  }
  function digest(value) {
    var bytes = new TextEncoder().encode(canonical(value));
    return "sha256:" + sha256(bytes);
  }
  /* Small, dependency-free SHA-256 (FIPS 180-4), used to make the playground's
     evidence chain genuinely verifiable in the browser. */
  function sha256(bytes) {
    var K = [
      0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,
      0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,
      0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,
      0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,
      0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,
      0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,
      0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,
      0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2
    ];
    var H = [0x6a09e667,0xbb67ae85,0x3c6ef372,0xa54ff53a,0x510e527f,0x9b05688c,0x1f83d9ab,0x5be0cd19];
    var bitLen = bytes.length * 8;
    var padded = new Uint8Array((((bytes.length + 9) + 63) >> 6) << 6);
    padded.set(bytes);
    padded[bytes.length] = 0x80;
    var view = new DataView(padded.buffer);
    var high = Math.floor(bitLen / 0x100000000);
    var low = bitLen >>> 0;
    view.setUint32(padded.length - 8, high, false);
    view.setUint32(padded.length - 4, low, false);
    function rotr(x, n) { return (x >>> n) | (x << (32 - n)); }
    var w = new Uint32Array(64);
    for (var offset = 0; offset < padded.length; offset += 64) {
      for (var t = 0; t < 16; t++) w[t] = view.getUint32(offset + t * 4, false);
      for (t = 16; t < 64; t++) {
        var s0 = rotr(w[t - 15], 7) ^ rotr(w[t - 15], 18) ^ (w[t - 15] >>> 3);
        var s1 = rotr(w[t - 2], 17) ^ rotr(w[t - 2], 19) ^ (w[t - 2] >>> 10);
        w[t] = (w[t - 16] + s0 + w[t - 7] + s1) | 0;
      }
      var a = H[0], b = H[1], c = H[2], d = H[3], e = H[4], f = H[5], g = H[6], h = H[7];
      for (t = 0; t < 64; t++) {
        var S1 = rotr(e, 6) ^ rotr(e, 11) ^ rotr(e, 25);
        var ch = (e & f) ^ ((~e) & g);
        var temp1 = (h + S1 + ch + K[t] + w[t]) | 0;
        var S0 = rotr(a, 2) ^ rotr(a, 13) ^ rotr(a, 22);
        var maj = (a & b) ^ (a & c) ^ (b & c);
        var temp2 = (S0 + maj) | 0;
        h = g; g = f; f = e; e = (d + temp1) | 0;
        d = c; c = b; b = a; a = (temp1 + temp2) | 0;
      }
      H[0] = (H[0] + a) | 0; H[1] = (H[1] + b) | 0; H[2] = (H[2] + c) | 0; H[3] = (H[3] + d) | 0;
      H[4] = (H[4] + e) | 0; H[5] = (H[5] + f) | 0; H[6] = (H[6] + g) | 0; H[7] = (H[7] + h) | 0;
    }
    return H.map(function (word) { return ("00000000" + (word >>> 0).toString(16)).slice(-8); }).join("");
  }
  function stateDoc() {
    return { tick: model.tick, mono_ms: model.tick, door: model.door, estop: model.estop,
      latched: model.latched, gate: model.gate, drive: model.drive, velocity_mm_s: model.velocity,
      parts: model.parts.map(function (p) { return { id: p.id, position_mm: p.position, route: p.route }; }),
      parts_delivered: model.delivered };
  }
  function stateHash() { return digest(stateDoc()); }
  function deviceSummary() {
    return {
      device_id: model.deviceId, display_name: "Playground conveyor workcell (model)", mode: "simulated",
      risk_class: "R1",
      capabilities: [
        { capability_id: "cap.world.step.v1", requires_permit: false, resource: "workcell", title: "Advance the model" },
        { capability_id: "cap.world.state.v1", requires_permit: false, resource: "workcell", title: "Read world state" },
        { capability_id: "cap.actuation.valve.v1", requires_permit: true, resource: "workcell", title: "Set diverter" },
        { capability_id: "cap.motion.stop.v1", requires_permit: false, resource: "workcell", title: "Stop the drive" }
      ],
      capability_ids: ["cap.world.step.v1", "cap.world.state.v1", "cap.actuation.valve.v1", "cap.motion.stop.v1"],
      resources: ["workcell"],
      fidelity: { engine: "playground-integer", fidelity_level: "F0", determinism: { kind: "exact" },
        timestep_ms: 1, realtime_factor: 0, reset: "full", snapshot_restore: true,
        gaps: ["No contact physics", "Parts are points", "The door and e-stop are simulated only"] },
      profile: { title: "Playground conveyor workcell",
        summary: "A small deterministic conveyor with a diverter, a safety door and an e-stop, used to demonstrate MHS receipts, idempotency, interlocks and evidence.",
        tags: ["conveyor", "deterministic simulation", "safety interlock"] }
    };
  }
  function manifest() {
    return {
      mhs_version: "1.0", device_id: model.deviceId, instance_id: model.instanceId,
      display_name: "Playground conveyor workcell (model)", mode: "simulated",
      resources: [{ resource_id: "workcell", kind: "world.sim", revision: model.revision,
        state: stateDoc(), state_schema: { type: "object" }, hash_exclusions: ["/mono_ms"] }],
      capabilities: deviceSummary().capabilities,
      safety: { risk_class: "R1", interlocks: interlocks(),
        estop: { kind: "software", latching: true, latency_ms: 50, engaged: model.latched },
        safe_state: { description: "Conveyor stopped, gate in main position", achieved_by: ["cap.motion.stop.v1"] } },
      fidelity: deviceSummary().fidelity,
      profile: deviceSummary().profile,
      conformance: { profile: "MHS-Sim", level: "CL4", issuer_kind: "self" }
    };
  }
  function interlocks() {
    var out = [{ id: "door_closed", state: model.door === "closed" ? "closed" : "open", source: "simulated" }];
    if (model.latched) out.push({ id: "estop", state: "open", description: "emergency stop latched" });
    return out;
  }
  function evidenceDigest(rec) {
    return digest({
      seq: rec.evidence.seq,
      prev_digest: rec.evidence.prev_digest,
      command_id: rec.command_id,
      capability_id: rec.capability_id,
      status: rec.status,
      state_revision_after: rec.state_revision_after,
      state_hash_after: rec.state_hash_after,
      input_digest: rec.input_digest
    });
  }
  function verifyChain() {
    var previous = model.genesisDigest;
    for (var i = 0; i < model.receipts.length; i++) {
      var rec = model.receipts[i];
      if (rec.evidence.prev_digest !== previous) return false;
      if (rec.evidence.digest !== evidenceDigest(rec)) return false;
      previous = rec.evidence.digest;
    }
    return previous === (model.receipts.length ? model.receipts[model.receipts.length - 1].evidence.digest : model.genesisDigest);
  }
  function receipt(capabilityId, input, status, output, error, replayed) {
    model.seq += 1;
    if (status === "completed") model.revision += 1;
    var previous = model.receipts.length ? model.receipts[model.receipts.length - 1].evidence.digest : model.genesisDigest;
    var inputDigest = digest(stripControl(input));
    var body = {
      receipt_id: "rcpt-playground-" + ("000000" + model.seq).slice(-6),
      command_id: input.__command_id,
      session_id: "mhs_s_playground_01",
      endpoint_id: model.endpointId,
      device_id: model.deviceId,
      capability_id: capabilityId,
      resource_ids: ["workcell"],
      input_digest: inputDigest,
      status: status,
      mode: "simulated",
      principal: { id: "playground", kind: "agent", display_name: "Browser playground" },
      accepted_at: new Date().toISOString(),
      ended_at: new Date().toISOString(),
      state_revision_before: Math.max(0, model.revision - (status === "completed" ? 1 : 0)),
      state_revision_after: model.revision,
      state_hash_after: stateHash(),
      output: output || null,
      replayed: !!replayed,
      effects: [{ kind: "simulation.advance", summary: capabilityId + " (" + status + ")", reversible: status !== "unknown", severity: "R1" }],
      evidence: { seq: model.seq, prev_digest: previous, digest: "" }
    };
    if (error) body.error = error;
    body.evidence.digest = evidenceDigest(body);
    model.receipts.push(body);
    return body;
  }
  function stripControl(input) {
    var copy = {};
    Object.keys(input || {}).forEach(function (key) {
      if (key !== "__command_id" && key !== "expected_revision") copy[key] = input[key];
    });
    return copy;
  }
  function errorResult(code, message, data) {
    return { code: code, message: message, data: data || {} };
  }
  function nowTick(ticks) {
    var n = Math.max(0, Math.min(10000, parseInt(ticks, 10) || 0));
    for (var i = 0; i < n; i++) {
      model.tick += 1;
      if (model.latched || model.door !== "closed") { model.velocity = 0; model.drive = "stopped"; continue; }
      model.velocity = model.drive === "running" ? 120 : 0;
      model.parts.forEach(function (part) {
        if (part.route === "stopped") return;
        part.position += model.velocity;
      });
      model.parts = model.parts.filter(function (part) {
        if (part.position > 1800) { model.delivered += 1; return false; }
        return true;
      });
    }
    return n;
  }
  function handle(request) {
    if (!request || typeof request !== "object") throw errorResult("MHS.PROTOCOL.INVALID_REQUEST", "Request must be a JSON object");
    if (request.jsonrpc !== "2.0") throw errorResult("MHS.PROTOCOL.INVALID_REQUEST", "jsonrpc must be '2.0'");
    var method = String(request.method || "");
    var name = method.indexOf("mhs.") === 0 ? method.slice(4) : method;
    var params = request.params || {};

    if (name === "hello") return HELLO;
    if (name === "devices.list") return { devices: [manifest()], count: 1 };
    if (name === "devices.get") return { device: manifest() };
    if (name === "schema.get") return { ref: params.ref || null, schema: { type: "object" } };
    if (name === "resource.read") {
      if (params.resource_id && params.resource_id !== "workcell") {
        throw errorResult("MHS.RESOURCE.UNKNOWN", "unknown resource '" + params.resource_id + "'");
      }
      return { device_id: model.deviceId, resource_id: "workcell", revision: model.revision,
        state: stateDoc(), state_hash: stateHash(), sampled_at: new Date().toISOString() };
    }
    if (name === "session.open") {
      if (params.mode && params.mode !== "simulated") {
        throw errorResult("MHS.SESSION.MODE_MISMATCH", "this endpoint exposes mode 'simulated', not '" + params.mode + "'");
      }
      model.sessionSeq += 1;
      return {
        session_id: "mhs_s_playground_" + ("00" + model.sessionSeq).slice(-2),
        endpoint_id: model.endpointId, device_ids: [model.deviceId], mode: "simulated",
        capabilities: deviceSummary().capability_ids,
        ttl_s: Number(params.ttl_s) || 600,
        issued_at: new Date().toISOString(),
        note: "Playground lease; no real capability is granted."
      };
    }
    if (name === "safety.status") {
      return { device_id: model.deviceId, mode: "simulated", risk_class: "R1", certified: false,
        estop: { kind: "software", latching: true, engaged: model.latched }, estop_engaged: model.latched,
        interlocks: interlocks(), safe_state: manifest().safety.safe_state, permits: [] };
    }
    if (name === "safety.estop") {
      model.latched = true; model.estop = "engaged"; model.drive = "stopped"; model.velocity = 0;
      var estopInput = { reason: params.reason || "stop", __command_id: params.command_id || nextCommandId() };
      return receipt("cap.internal.safety_estop.v1", estopInput, "completed", { estop: "engaged", latched: true });
    }
    if (name === "safety.reset") {
      var resetInput = { __command_id: params.command_id || nextCommandId() };
      if (model.door !== "closed") {
        return receipt("cap.internal.safety_reset.v1", resetInput, "rejected", null,
          { mhs_code: "MHS.SAFETY.INTERLOCK_OPEN", message: "close the safety door before resetting", interlocks: interlocks() });
      }
      model.latched = false; model.estop = "released"; model.drive = "stopped"; model.velocity = 0;
      return receipt("cap.internal.safety_reset.v1", resetInput, "completed", { estop: "released", latched: false, safe_state: true });
    }
    if (name === "evidence.export") {
      var head = model.receipts.length ? model.receipts[model.receipts.length - 1].evidence.digest : model.genesisDigest;
      return { bundle_version: "1.0.0",
        endpoint_info: { endpoint_id: model.endpointId, mhs_version: "1.0",
          server: { name: "mhs-playground", version: "1.0.0" }, genesis_digest: model.genesisDigest },
        created_at: new Date().toISOString(), receipts: model.receipts.slice(),
        head_digest: head, chain_valid: verifyChain(),
        genesis: { kind: "genesis", seq: 0, genesis_document: { endpoint_id: model.endpointId }, digest: model.genesisDigest },
        count: model.receipts.length,
        note: "Playground model only. Digests are real SHA-256 values over the browser state, but this is not a safety-rated evidence system." };
    }
    if (name === "command") {
      var capabilityId = params.capability_id;
      var input = Object.assign({}, params.input || {});
      input.__command_id = params.command_id || nextCommandId();
      if (params.expected_revision != null && Number(params.expected_revision) !== model.revision) {
        return receipt(capabilityId, input, "rejected", null,
          { mhs_code: "MHS.CONFLICT.REVISION", message: "expected revision " + params.expected_revision + " but current revision is " + model.revision, current_revision: model.revision });
      }
      var cached = model.commandIds[input.__command_id];
      if (cached) {
        if (cached.digest === digest(stripControl(input))) {
          var replay = JSON.parse(JSON.stringify(cached.receipt));
          replay.replayed = true;
          return replay;
        }
        return receipt(capabilityId, input, "rejected", null, { mhs_code: "MHS.CONFLICT.COMMAND_ID_REUSE", message: "command_id was already used with different input" });
      }
      if (model.latched) {
        var refused = receipt(capabilityId, input, "rejected", null, { mhs_code: "MHS.SAFETY.ESTOP_ENGAGED", message: "device is latched by an emergency stop" });
        model.commandIds[input.__command_id] = { digest: digest(stripControl(input)), receipt: refused };
        return refused;
      }
      if (capabilityId === "cap.world.step.v1") {
        if (model.door !== "closed") {
          var stepBlocked = receipt(capabilityId, input, "rejected", null,
            { mhs_code: "MHS.SAFETY.INTERLOCK_OPEN", message: "required interlock is not closed: door_closed", interlocks: interlocks() });
          model.commandIds[input.__command_id] = { digest: digest(stripControl(input)), receipt: stepBlocked };
          return stepBlocked;
        }
        var n = nowTick(input.ticks);
        var ok = receipt(capabilityId, input, "completed", { tick: model.tick, stepped: n, state_hash: stateHash() });
        model.commandIds[input.__command_id] = { digest: digest(stripControl(input)), receipt: ok };
        return ok;
      }
      if (capabilityId === "cap.actuation.valve.v1") {
        if (model.door !== "closed") {
          var blocked = receipt(capabilityId, input, "rejected", null,
            { mhs_code: "MHS.SAFETY.INTERLOCK_OPEN", message: "required interlock is not closed: door_closed", interlocks: interlocks() });
          model.commandIds[input.__command_id] = { digest: digest(stripControl(input)), receipt: blocked };
          return blocked;
        }
        if (!params.permit_id) {
          var permit = receipt(capabilityId, input, "rejected", null,
            { mhs_code: "MHS.SAFETY.PERMIT_REQUIRED", message: "capability 'cap.actuation.valve.v1' requires an approved permit" });
          model.commandIds[input.__command_id] = { digest: digest(stripControl(input)), receipt: permit };
          return permit;
        }
        model.gate = input.gate === "divert" ? "divert" : "main";
        var done = receipt(capabilityId, input, "completed", { gate: model.gate });
        model.commandIds[input.__command_id] = { digest: digest(stripControl(input)), receipt: done };
        return done;
      }
      if (capabilityId === "cap.motion.stop.v1") {
        model.drive = "stopped"; model.velocity = 0;
        var stopped = receipt(capabilityId, input, "completed", { drive: "stopped", velocity_mm_s: 0, safe_state_achieved: true });
        model.commandIds[input.__command_id] = { digest: digest(stripControl(input)), receipt: stopped };
        return stopped;
      }
      var unknown = receipt(capabilityId, input, "rejected", null,
        { mhs_code: "MHS.CAPABILITY.UNKNOWN", message: "device does not expose capability '" + capabilityId + "'" });
      model.commandIds[input.__command_id] = { digest: digest(stripControl(input)), receipt: unknown };
      return unknown;
    }
    throw errorResult("MHS.PROTOCOL.METHOD_NOT_FOUND", "unknown method '" + method + "'");
  }
  function nextCommandId() { counter += 1; return "01J8ZQ" + ("00000" + counter).slice(-5) + "PLAYCMD0"; }

  /* ---- rendering ---- */
  function setText(id, value) { var node = document.getElementById(id); if (node) node.textContent = value == null ? "—" : value; }
  function renderState() {
    setText("state-tick", model.tick);
    setText("state-revision", model.revision);
    setText("state-door", model.door);
    setText("state-estop", model.estop + (model.latched ? " (latched)" : ""));
    setText("state-parts", model.parts.length + " on belt, " + model.delivered + " delivered");
    setText("state-evidence", model.receipts.length + " receipts");
    var doorBtn = document.getElementById("toggle-door");
    if (doorBtn) doorBtn.textContent = model.door === "closed" ? "Open safety door" : "Close safety door";
  }
  function renderReceipt(rec) {
    if (!receiptCard) return;
    if (!rec) { receiptCard.hidden = true; return; }
    receiptCard.hidden = false;
    setText("receipt-status", rec.status);
    setText("receipt-command", rec.command_id);
    setText("receipt-revision", rec.state_revision_after);
    setText("receipt-hash", rec.state_hash_after);
    setText("receipt-seq", rec.evidence ? rec.evidence.seq : "—");
    setText("receipt-replayed", rec.replayed ? "yes (retained receipt returned)" : "no (executed)");
    var note = document.getElementById("receipt-note");
    if (note) {
      note.textContent = rec.status === "rejected"
        ? "A rejection is a receipt, not an exception: the refusal is recorded and chained, and the revision did not advance."
        : rec.replayed ? "The same command_id and input returned the retained receipt; no second physical action." : "Completed command: the revision advanced and the state hash is chained into the evidence log.";
    }
  }
  function log(line) {
    if (!logEl) return;
    var li = document.createElement("li");
    var time = document.createElement("time");
    time.textContent = new Date().toLocaleTimeString();
    li.appendChild(time);
    li.appendChild(document.createTextNode(line));
    logEl.insertBefore(li, logEl.firstChild);
    while (logEl.children.length > 60) logEl.removeChild(logEl.lastChild);
  }
  function send() {
    if (errorEl) { errorEl.hidden = true; errorEl.textContent = ""; }
    var request;
    try { request = JSON.parse(editor.value); }
    catch (err) {
      if (errorEl) { errorEl.hidden = false; errorEl.textContent = "Request is not valid JSON: " + err.message; }
      return;
    }
    var started = performance.now();
    try {
      var result = handle(request);
      var payload = { jsonrpc: "2.0", id: request.id == null ? null : request.id, result: result };
      if (respJson) respJson.textContent = JSON.stringify(payload, null, 2);
      if (respStatus) respStatus.innerHTML = "";
      badge(respStatus, "200 OK", "badge-good");
      badge(respStatus, request.method, "badge-muted");
      badge(respStatus, Math.max(0.1, performance.now() - started).toFixed(1) + " ms", "badge-muted");
      setText("response-method", request.method || "—");
      setText("response-code", "200 OK");
      setText("response-mode", "simulated");
      if (result && result.receipt_id) renderReceipt(result); else renderReceipt(null);
      renderState();
      log(request.method + " → " + (result && result.status ? result.status : "ok"));
    } catch (err) {
      var error = err && err.code ? err : errorResult("MHS.PROTOCOL.INTERNAL_ERROR", String(err));
      var payloadErr = { jsonrpc: "2.0", id: request.id == null ? null : request.id,
        error: { code: -32000, message: error.message, data: { mhs_code: error.code } } };
      if (respJson) respJson.textContent = JSON.stringify(payloadErr, null, 2);
      if (respStatus) { respStatus.innerHTML = ""; badge(respStatus, error.code, "badge-bad"); }
      setText("response-method", request.method || "—");
      setText("response-code", error.code);
      setText("response-mode", "simulated");
      renderReceipt(null);
      log(request.method + " → error " + error.code);
    }
  }
  function badge(parent, text, variant) {
    if (!parent) return;
    var span = document.createElement("span");
    span.className = "badge " + (variant || "badge-muted");
    span.textContent = text;
    parent.appendChild(span);
  }

  /* ---- scenarios ---- */
  var scenarios = {
    hello: { jsonrpc: "2.0", id: "req-hello", method: "mhs.hello", params: { client: { name: "mhs-playground", version: "1.0" }, protocol_versions: ["1.0"] } },
    devices: { jsonrpc: "2.0", id: "req-devices", method: "mhs.devices.list", params: {} },
    get: { jsonrpc: "2.0", id: "req-get", method: "mhs.devices.get", params: {} },
    read: { jsonrpc: "2.0", id: "req-read", method: "mhs.resource.read", params: { resource_id: "workcell" } },
    step: { jsonrpc: "2.0", id: "req-step", method: "mhs.command", params: { capability_id: "cap.world.step.v1", command_id: "01J8ZQ00001PLAYCMD01", input: { ticks: 120 } } },
    duplicate: { jsonrpc: "2.0", id: "req-dup", method: "mhs.command", params: { capability_id: "cap.world.step.v1", command_id: "01J8ZQ00001PLAYCMD01", input: { ticks: 120 } } },
    stale: { jsonrpc: "2.0", id: "req-stale", method: "mhs.command", params: { capability_id: "cap.world.step.v1", command_id: "01J8ZQ00002PLAYCMD02", expected_revision: 0, input: { ticks: 10 } } },
    interlock: { jsonrpc: "2.0", id: "req-interlock", method: "mhs.command", params: { capability_id: "cap.actuation.valve.v1", command_id: "01J8ZQ00003PLAYCMD03", input: { gate: "divert" } } },
    safety: { jsonrpc: "2.0", id: "req-safety", method: "mhs.safety.status", params: {} },
    estop: { jsonrpc: "2.0", id: "req-estop", method: "mhs.safety.estop", params: { reason: "playground scenario" } },
    evidence: { jsonrpc: "2.0", id: "req-evidence", method: "mhs.evidence.export", params: {} }
  };

  document.addEventListener("click", function (event) {
    var button = event.target.closest("[data-scenario]");
    if (!button) return;
    var name = button.getAttribute("data-scenario");
    if (name === "interlock") model.door = "open";
    if (name === "hello" || name === "reset") { /* no-op */ }
    var scenario = scenarios[name];
    if (!scenario) return;
    editor.value = JSON.stringify(scenario, null, 2);
    document.querySelectorAll("[data-scenario]").forEach(function (item) { item.classList.remove("is-active"); });
    button.classList.add("is-active");
    log("scenario: " + name);
    send();
  });
  if (sendBtn) sendBtn.addEventListener("click", send);
  if (formatBtn) formatBtn.addEventListener("click", function () {
    try { editor.value = JSON.stringify(JSON.parse(editor.value), null, 2); }
    catch (err) { if (errorEl) { errorEl.hidden = false; errorEl.textContent = err.message; } }
  });
  if (resetBtn) resetBtn.addEventListener("click", function () {
    editor.value = JSON.stringify(scenarios.hello, null, 2);
    if (errorEl) errorEl.hidden = true;
    if (respJson) respJson.textContent = "// Send a request to see the response.";
    renderReceipt(null);
    log("request reset");
  });
  var doorBtn = document.getElementById("toggle-door");
  if (doorBtn) doorBtn.addEventListener("click", function () {
    model.door = model.door === "closed" ? "open" : "closed";
    log("physical door set to " + model.door + " (not an MHS command)");
    renderState();
  });
  var resetModel = document.getElementById("reset-model");
  if (resetModel) resetModel.addEventListener("click", function () {
    model = freshModel(); renderState(); renderReceipt(null); log("model reset");
  });
  var clearLog = document.getElementById("clear-log");
  if (clearLog) clearLog.addEventListener("click", function () { if (logEl) logEl.innerHTML = ""; });

  editor.addEventListener("keydown", function (event) {
    if ((event.metaKey || event.ctrlKey) && event.key === "Enter") { event.preventDefault(); send(); }
  });
  renderState();
  log("playground model ready — reference implementation only");
})();
