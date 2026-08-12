import fnmatch
import json
import os
import re
import sys
import tkinter as tk
from tkinter import ttk, messagebox

APP_NAME = "BloodlessAPI"
VERSION = "1.0"

HTTP_METHODS = ("get", "post", "put", "patch", "delete", "head", "options", "trace")
METHOD_COLORS = {
    "GET": "#1f9d63",
    "POST": "#2563eb",
    "PUT": "#c47612",
    "PATCH": "#8b3ff0",
    "DELETE": "#dc2f34",
    "HEAD": "#64707e",
    "OPTIONS": "#64707e",
    "TRACE": "#64707e",
}

METHOD_COLORS_DARK = {
    "GET": "#33a06f",
    "POST": "#3b82f6",
    "PUT": "#d98324",
    "PATCH": "#a855f7",
    "DELETE": "#ef4444",
    "HEAD": "#7c8695",
    "OPTIONS": "#7c8695",
    "TRACE": "#7c8695",
}

THEMES = {
    "dark": {
        "bg": "#0d0d10",
        "panel": "#15151a",
        "elevated": "#1d1d24",
        "border": "#2a2a33",
        "hover": "#23232b",
        "fg": "#e7e7ec",
        "dim": "#9a9aa6",
        "faint": "#63636f",
        "ok": "#33a06f",
        "accent": "#d9313c",
        "accent_fg": "#ffffff",
        "accent_hover": "#e84a54",
        "accent_press": "#ad2029",
        "accent_soft": "#251419",
        "accent2": "#ef6b73",
        "sel": "#2a1a20",
        "sel_fg": "#f4eaec",
        "stripe": "#131318",
        "danger": "#ef4444",
        "code_bg": "#0f0f13",
        "code_fg": "#d7d7de",
    },
    "light": {
        "bg": "#f3efe7",
        "panel": "#faf7f0",
        "elevated": "#fffdf8",
        "border": "#e3dccd",
        "hover": "#ece6d9",
        "fg": "#33302a",
        "dim": "#6e685d",
        "faint": "#9c9587",
        "ok": "#2c8c58",
        "accent": "#c0303a",
        "accent_fg": "#ffffff",
        "accent_hover": "#d0434d",
        "accent_press": "#9c1f27",
        "accent_soft": "#f6e5e1",
        "accent2": "#a83039",
        "sel": "#f4e2dc",
        "sel_fg": "#3b1a1b",
        "stripe": "#efe9dd",
        "danger": "#c33036",
        "code_bg": "#efe9dd",
        "code_fg": "#37342d",
    },
}

INTERESTING = [
    ("admin", "admin surface"),
    ("internal", "internal surface"),
    ("debug", "debug surface"),
    ("test", "test surface"),
    ("upload", "file upload"),
    ("download", "file retrieval"),
    ("file", "file handling"),
    ("import", "data import"),
    ("export", "data export"),
    ("token", "credential material"),
    ("password", "credential material"),
    ("secret", "credential material"),
    ("key", "credential material"),
    ("auth", "authentication"),
    ("login", "authentication"),
    ("session", "session handling"),
    ("user", "user object"),
    ("account", "account object"),
    ("role", "authorization"),
    ("permission", "authorization"),
    ("redirect", "redirect param"),
    ("url", "url param"),
    ("callback", "callback param"),
    ("proxy", "proxy behaviour"),
    ("query", "raw query param"),
    ("sql", "raw query param"),
    ("filter", "filter param"),
    ("search", "search param"),
    ("exec", "command surface"),
    ("cmd", "command surface"),
    ("command", "command surface"),
    ("config", "configuration"),
    ("setting", "configuration"),
    ("graphql", "graphql surface"),
    ("webhook", "webhook surface"),
    ("v1", "versioned path"),
    ("legacy", "legacy path"),
    ("deprecated", "deprecated path"),
]

def as_dict(x):
    return x if isinstance(x, dict) else {}

def as_list(x):
    if isinstance(x, list):
        return x
    if x is None:
        return []
    return [x]

def text_of(x):
    if x is None:
        return ""
    if isinstance(x, str):
        return x.strip()
    return str(x)

class RefResolver:
    def __init__(self, root):
        self.root = root if isinstance(root, dict) else {}

    def resolve(self, node, seen=None):
        if seen is None:
            seen = set()
        if not isinstance(node, dict):
            return node
        ref = node.get("$ref")
        if isinstance(ref, str) and ref.startswith("#/"):
            if ref in seen:
                return {"type": "object", "description": "recursive: " + ref}
            seen = seen | {ref}
            target = self.root
            for part in ref[2:].split("/"):
                part = part.replace("~1", "/").replace("~0", "~")
                if isinstance(target, dict) and part in target:
                    target = target[part]
                elif isinstance(target, list) and part.isdigit() and int(part) < len(target):
                    target = target[int(part)]
                else:
                    return {"description": "unresolved: " + ref}
            merged = self.resolve(target, seen)
            rest = {k: v for k, v in node.items() if k != "$ref"}
            if isinstance(merged, dict) and rest:
                out = dict(merged)
                out.update(rest)
                return out
            return merged
        return node

    def deep(self, node, seen=frozenset(), depth=0):
        if depth > 24:
            return node
        if isinstance(node, dict):
            ref = node.get("$ref")
            if isinstance(ref, str) and ref.startswith("#/"):
                if ref in seen:
                    return {"type": "object",
                            "description": "recursive -> " + ref.split("/")[-1]}
                resolved = self.resolve(node)
                return self.deep(resolved, seen | {ref}, depth + 1)
            return {k: self.deep(v, seen, depth + 1) for k, v in node.items()}
        if isinstance(node, list):
            return [self.deep(v, seen, depth + 1) for v in node]
        return node

def schema_example(schema, depth=0):
    if depth > 8 or not isinstance(schema, dict):
        return None
    for key in ("example", "default"):
        if key in schema and schema[key] is not None:
            return schema[key]
    if isinstance(schema.get("examples"), list) and schema["examples"]:
        return schema["examples"][0]
    if isinstance(schema.get("enum"), list) and schema["enum"]:
        return schema["enum"][0]
    for combiner in ("allOf", "anyOf", "oneOf"):
        if isinstance(schema.get(combiner), list) and schema[combiner]:
            if combiner == "allOf":
                merged = {}
                for part in schema[combiner]:
                    sub = schema_example(part, depth + 1)
                    if isinstance(sub, dict):
                        merged.update(sub)
                if merged:
                    return merged
            return schema_example(schema[combiner][0], depth + 1)
    stype = schema.get("type")
    if isinstance(stype, list):
        stype = next((t for t in stype if t != "null"), None)
    if stype == "object" or "properties" in schema:
        out = {}
        for name, sub in as_dict(schema.get("properties")).items():
            out[name] = schema_example(sub, depth + 1)
        if not out and schema.get("additionalProperties"):
            out["key"] = schema_example(schema["additionalProperties"], depth + 1)
        return out
    if stype == "array":
        return [schema_example(schema.get("items", {}), depth + 1)]
    if stype == "integer":
        return 0
    if stype == "number":
        return 0.0
    if stype == "boolean":
        return True
    if stype == "null":
        return None
    fmt = schema.get("format") or ""
    return {
        "date-time": "2024-01-01T00:00:00Z",
        "date": "2024-01-01",
        "uuid": "00000000-0000-0000-0000-000000000000",
        "email": "user@example.com",
        "uri": "https://example.com",
        "url": "https://example.com",
        "password": "string",
        "binary": "<binary>",
        "byte": "c3RyaW5n",
    }.get(fmt, "string")

def schema_summary(schema, depth=0, max_depth=6):
    if not isinstance(schema, dict):
        return "-"
    if depth > max_depth:
        return "..."
    stype = schema.get("type")
    if isinstance(stype, list):
        stype = "|".join(str(t) for t in stype)
    if "properties" in schema or stype == "object":
        required = set(x for x in as_list(schema.get("required")) if isinstance(x, str))
        lines = []
        for name, sub in as_dict(schema.get("properties")).items():
            sub = sub if isinstance(sub, dict) else {}
            mark = "*" if name in required else " "
            tdesc = sub.get("type") or ("object" if "properties" in sub else "any")
            if isinstance(tdesc, list):
                tdesc = "|".join(str(t) for t in tdesc)
            if sub.get("format"):
                tdesc = "%s(%s)" % (tdesc, sub["format"])
            if isinstance(sub.get("enum"), list):
                tdesc += " enum=" + ", ".join(str(e) for e in sub["enum"][:6])
            note = text_of(sub.get("description"))
            line = "  %s %-24s %s" % (mark, name, tdesc)
            if note:
                line += "  - " + note.splitlines()[0][:90]
            lines.append(line)
            if "properties" in sub and depth < max_depth:
                nested = schema_summary(sub, depth + 1, max_depth)
                for nl in nested.splitlines():
                    lines.append("  " + nl)
        if not lines:
            return "object (free-form)"
        return "\n".join(lines)
    if stype == "array":
        inner = schema_summary(schema.get("items", {}), depth + 1, max_depth)
        return "array of:\n" + "\n".join("  " + l for l in inner.splitlines())
    bits = [stype or "any"]
    if schema.get("format"):
        bits.append("format=" + str(schema["format"]))
    if isinstance(schema.get("enum"), list):
        bits.append("enum=" + ", ".join(str(e) for e in schema["enum"][:8]))
    if schema.get("description"):
        bits.append("- " + text_of(schema["description"]).splitlines()[0][:90])
    return " ".join(bits)

def flag_notes(ep):
    notes = []
    hay = (ep["path"] + " " + ep.get("summary", "") + " " +
           " ".join(p["name"] for p in ep["params"])).lower()
    seen = set()
    for word, label in INTERESTING:
        if re.search(r"(?<![a-z])" + re.escape(word), hay) and label not in seen:
            seen.add(label)
            notes.append(label)
    if not ep.get("auth"):
        notes.append("no auth declared on this operation")
    if "{" in ep["path"] or ":" in ep["path"].split("?")[0]:
        notes.append("path parameter")
    if ep["method"] in ("PUT", "DELETE", "PATCH"):
        notes.append("state-changing method")
    return notes[:10]

def new_endpoint(**kw):
    ep = {
        "method": "GET",
        "path": "/",
        "server": "",
        "summary": "",
        "description": "",
        "tags": [],
        "deprecated": False,
        "params": [],
        "headers": [],
        "body_type": "",
        "body_example": "",
        "body_schema": "",
        "auth": "",
        "responses": [],
        "source": "",
        "raw": None,
    }
    ep.update(kw)
    return ep

def parse_openapi(doc):
    rr = RefResolver(doc)
    is_v2 = str(doc.get("swagger", "")).startswith("2")
    servers = []
    if is_v2:
        host = text_of(doc.get("host"))
        base = text_of(doc.get("basePath"))
        schemes = as_list(doc.get("schemes")) or ["https"]
        if host:
            servers.append("%s://%s%s" % (schemes[0], host, base))
        elif base:
            servers.append(base)
    else:
        for srv in as_list(doc.get("servers")):
            url = text_of(as_dict(srv).get("url"))
            for var, spec in as_dict(as_dict(srv).get("variables")).items():
                dflt = text_of(as_dict(spec).get("default"))
                if dflt:
                    url = url.replace("{%s}" % var, dflt)
            if url:
                servers.append(url)
    server = servers[0] if servers else ""
    if is_v2:
        schemes_def = as_dict(doc.get("securityDefinitions"))
    else:
        schemes_def = as_dict(as_dict(doc.get("components")).get("securitySchemes"))

    def describe_security(sec_list):
        out = []
        for entry in as_list(sec_list):
            for name, scopes in as_dict(entry).items():
                spec = rr.resolve(as_dict(schemes_def.get(name)))
                stype = text_of(spec.get("type"))
                if stype in ("apiKey",):
                    detail = "apiKey in %s named %s" % (spec.get("in"), spec.get("name"))
                elif stype in ("http",):
                    detail = "http %s" % spec.get("scheme")
                elif stype in ("oauth2", "openIdConnect"):
                    detail = stype
                elif stype == "basic":
                    detail = "http basic"
                else:
                    detail = stype or "declared"
                if scopes:
                    detail += " scopes=" + ",".join(str(s) for s in as_list(scopes))
                out.append("%s (%s)" % (name, detail))
        return "; ".join(out)

    global_security = describe_security(doc.get("security"))
    endpoints = []
    for path, item in as_dict(doc.get("paths")).items():
        item = rr.resolve(as_dict(item))
        shared_params = as_list(item.get("parameters"))
        for method, op in item.items():
            if method.lower() not in HTTP_METHODS:
                continue
            op = rr.resolve(as_dict(op))
            ep = new_endpoint(
                method=method.upper(),
                path=path,
                server=server,
                summary=text_of(op.get("summary")) or text_of(op.get("operationId")),
                description=text_of(op.get("description")),
                tags=[text_of(t) for t in as_list(op.get("tags"))],
                deprecated=bool(op.get("deprecated")),
                source="OpenAPI 2.0" if is_v2 else "OpenAPI 3.x",
                raw=op,
            )
            if "security" in op:
                ep["auth"] = describe_security(op.get("security"))
            else:
                ep["auth"] = global_security
            for prm in shared_params + as_list(op.get("parameters")):
                prm = rr.resolve(as_dict(prm))
                loc = text_of(prm.get("in"))
                if is_v2 and loc == "body":
                    sch = rr.deep(as_dict(prm.get("schema")))
                    ep["body_type"] = (as_list(doc.get("consumes")) or ["application/json"])[0]
                    ep["body_schema"] = schema_summary(sch)
                    ep["body_example"] = json.dumps(schema_example(sch), indent=2)
                    continue
                sch = rr.deep(as_dict(prm.get("schema"))) or {}
                ptype = text_of(prm.get("type")) or text_of(sch.get("type")) or "string"
                ep["params"].append({
                    "name": text_of(prm.get("name")),
                    "loc": loc or "query",
                    "required": bool(prm.get("required")) or loc == "path",
                    "type": ptype,
                    "desc": text_of(prm.get("description")),
                    "example": prm.get("example", schema_example(sch) if sch else None),
                })
            body = rr.resolve(as_dict(op.get("requestBody")))
            content = as_dict(body.get("content"))
            if content:
                ctype = next(iter(content))
                sch = rr.deep(as_dict(as_dict(content[ctype]).get("schema")))
                ep["body_type"] = ctype
                ep["body_schema"] = schema_summary(sch)
                sample = as_dict(content[ctype]).get("example")
                if sample is None:
                    sample = schema_example(sch)
                ep["body_example"] = json.dumps(sample, indent=2, default=str)
                if body.get("required"):
                    ep["body_type"] += " (required)"
            for code, resp in as_dict(op.get("responses")).items():
                resp = rr.resolve(as_dict(resp))
                rbody = ""
                rcontent = as_dict(resp.get("content"))
                if rcontent:
                    rtype = next(iter(rcontent))
                    rsch = rr.deep(as_dict(as_dict(rcontent[rtype]).get("schema")))
                    rbody = rtype + "\n" + schema_summary(rsch)
                elif "schema" in resp:
                    rbody = schema_summary(rr.deep(as_dict(resp.get("schema"))))
                endpoint_headers = as_dict(resp.get("headers"))
                if endpoint_headers:
                    rbody += "\nheaders: " + ", ".join(endpoint_headers.keys())
                ep["responses"].append({
                    "code": str(code),
                    "desc": text_of(resp.get("description")),
                    "body": rbody,
                })
            endpoints.append(ep)
    title = text_of(as_dict(doc.get("info")).get("title")) or "API"
    return endpoints, title, servers

def _postman_url(url):
    if isinstance(url, str):
        return url, []
    url = as_dict(url)
    raw = text_of(url.get("raw"))
    query = []
    for q in as_list(url.get("query")):
        q = as_dict(q)
        if q.get("disabled"):
            continue
        query.append({
            "name": text_of(q.get("key")),
            "loc": "query",
            "required": False,
            "type": "string",
            "desc": text_of(q.get("description")),
            "example": q.get("value"),
        })
    if not raw:
        host = url.get("host")
        host = ".".join(host) if isinstance(host, list) else text_of(host)
        segs = url.get("path")
        segs = "/".join(str(s) for s in segs) if isinstance(segs, list) else text_of(segs)
        proto = text_of(url.get("protocol")) or "https"
        raw = "%s://%s/%s" % (proto, host, segs.lstrip("/"))
    return raw, query

def _split_url(raw):
    m = re.match(r"^([a-zA-Z][a-zA-Z0-9+.\-]*://[^/?#]+)(.*)$", raw)
    if m:
        server, rest = m.group(1), m.group(2)
    else:
        server, rest = "", raw
    path = rest.split("?")[0].split("#")[0]
    if not path.startswith("/"):
        path = "/" + path
    return server, path

def _postman_auth(auth):
    auth = as_dict(auth)
    atype = text_of(auth.get("type"))
    if not atype:
        return ""
    detail = []
    for entry in as_list(auth.get(atype)):
        entry = as_dict(entry)
        if entry.get("key"):
            detail.append("%s=%s" % (entry["key"], entry.get("value")))
    return atype + (" [" + ", ".join(detail) + "]" if detail else "")

def parse_postman(doc):
    endpoints = []
    servers = set()
    collection_auth = _postman_auth(doc.get("auth"))

    def walk(items, trail, inherited_auth):
        for item in as_list(items):
            item = as_dict(item)
            name = text_of(item.get("name"))
            auth = _postman_auth(item.get("auth")) or inherited_auth
            if item.get("item"):
                walk(item["item"], trail + [name], auth)
                continue
            req = item.get("request")
            if isinstance(req, str):
                req = {"method": "GET", "url": req}
            req = as_dict(req)
            if not req:
                continue
            raw, query = _postman_url(req.get("url"))
            server, path = _split_url(raw)
            if server:
                servers.add(server)
            ep = new_endpoint(
                method=text_of(req.get("method")).upper() or "GET",
                path=path,
                server=server,
                summary=name,
                description=text_of(as_dict(req.get("description")).get("content")
                                    if isinstance(req.get("description"), dict)
                                    else req.get("description")),
                tags=[t for t in trail if t],
                params=query,
                auth=_postman_auth(req.get("auth")) or auth,
                source="Postman collection",
                raw=item,
            )
            for h in as_list(req.get("header")):
                h = as_dict(h)
                if h.get("disabled"):
                    continue
                ep["headers"].append({"name": text_of(h.get("key")),
                                      "value": text_of(h.get("value"))})
            for seg in re.findall(r"[:{]([A-Za-z0-9_\-]+)}?", path):
                ep["params"].append({"name": seg, "loc": "path", "required": True,
                                     "type": "string", "desc": "", "example": None})
            body = as_dict(req.get("body"))
            mode = text_of(body.get("mode"))
            if mode == "raw":
                ep["body_type"] = "raw"
                lang = as_dict(as_dict(body.get("options")).get("raw")).get("language")
                if lang:
                    ep["body_type"] = "raw (%s)" % lang
                ep["body_example"] = text_of(body.get("raw"))
            elif mode in ("urlencoded", "formdata"):
                ep["body_type"] = ("application/x-www-form-urlencoded"
                                   if mode == "urlencoded" else "multipart/form-data")
                fields = []
                for f in as_list(body.get(mode)):
                    f = as_dict(f)
                    if f.get("disabled"):
                        continue
                    fields.append("  %-24s %s" % (text_of(f.get("key")),
                                                  text_of(f.get("type") or "text")))
                    ep["body_example"] += "%s=%s&" % (text_of(f.get("key")),
                                                      text_of(f.get("value")))
                ep["body_schema"] = "\n".join(fields)
                ep["body_example"] = ep["body_example"].rstrip("&")
            elif mode == "graphql":
                ep["body_type"] = "graphql"
                ep["body_example"] = json.dumps(body.get("graphql"), indent=2)
            for resp in as_list(item.get("response")):
                resp = as_dict(resp)
                ep["responses"].append({
                    "code": str(resp.get("code") or ""),
                    "desc": text_of(resp.get("name") or resp.get("status")),
                    "body": text_of(resp.get("body"))[:2000],
                })
            endpoints.append(ep)

    walk(doc.get("item"), [], collection_auth)
    title = text_of(as_dict(doc.get("info")).get("name")) or "Postman collection"
    return endpoints, title, sorted(servers)

def parse_har(doc):
    endpoints = []
    servers = set()
    seen = set()
    for entry in as_list(as_dict(doc.get("log")).get("entries")):
        req = as_dict(as_dict(entry).get("request"))
        raw = text_of(req.get("url"))
        if not raw:
            continue
        server, path = _split_url(raw)
        method = text_of(req.get("method")).upper() or "GET"
        key = (method, server, path)
        if key in seen:
            continue
        seen.add(key)
        if server:
            servers.add(server)
        ep = new_endpoint(method=method, path=path, server=server,
                          source="HAR capture", raw=req)
        for q in as_list(req.get("queryString")):
            q = as_dict(q)
            ep["params"].append({"name": text_of(q.get("name")), "loc": "query",
                                 "required": False, "type": "string", "desc": "",
                                 "example": q.get("value")})
        for h in as_list(req.get("headers")):
            h = as_dict(h)
            name = text_of(h.get("name"))
            if name.lower().startswith(":"):
                continue
            ep["headers"].append({"name": name, "value": text_of(h.get("value"))})
            if name.lower() in ("authorization", "x-api-key", "cookie"):
                ep["auth"] = name + " header present in capture"
        post = as_dict(req.get("postData"))
        if post:
            ep["body_type"] = text_of(post.get("mimeType"))
            ep["body_example"] = text_of(post.get("text"))
            params = as_list(post.get("params"))
            if params:
                ep["body_schema"] = "\n".join(
                    "  %-24s %s" % (text_of(as_dict(p).get("name")),
                                    text_of(as_dict(p).get("value"))[:60])
                    for p in params)
        resp = as_dict(as_dict(entry).get("response"))
        if resp:
            ep["responses"].append({
                "code": str(resp.get("status") or ""),
                "desc": text_of(resp.get("statusText")),
                "body": text_of(as_dict(resp.get("content")).get("mimeType")),
            })
        endpoints.append(ep)
    return endpoints, "HAR capture", sorted(servers)

PATH_RE = re.compile(r"^/[A-Za-z0-9_\-./{}:$%~]*$")
URL_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.\-]*://[^\s\"']+$")
METHOD_PREFIX_RE = re.compile(r"^\s*(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)\s+(\S+)",
                              re.IGNORECASE)

def parse_generic(doc):
    found = {}
    servers = set()
    paths_seen = set()
    pending_weak = []
    second_pass = [False]

    def record(method, raw_path, node, trail, weak=False):
        if weak and not second_pass[0]:
            pending_weak.append((method, raw_path, node, trail))
            return
        server, path = _split_url(raw_path) if URL_RE.match(raw_path) else ("", raw_path)
        if server:
            servers.add(server)
        if not path.startswith("/"):
            path = "/" + path
        key = (method.upper(), server, path)
        if key in found:
            return
        if weak and (server, path) in paths_seen:
            return
        paths_seen.add((server, path))
        node = as_dict(node)
        ep = new_endpoint(method=method.upper(), path=path, server=server,
                          summary=text_of(node.get("name") or node.get("summary")
                                          or node.get("title") or node.get("description"))[:120],
                          tags=[t for t in trail[:2] if t],
                          source="heuristic scan", raw=node if node else None)
        for pname in re.findall(r"[{:]([A-Za-z0-9_\-]+)}?", path):
            ep["params"].append({"name": pname, "loc": "path", "required": True,
                                 "type": "string", "desc": "", "example": None})
        for pkey in ("params", "parameters", "query", "queryParams", "args"):
            val = node.get(pkey)
            if isinstance(val, dict):
                for k, v in val.items():
                    ep["params"].append({"name": str(k), "loc": "query", "required": False,
                                         "type": type(v).__name__, "desc": "", "example": v})
            elif isinstance(val, list):
                for v in val:
                    if isinstance(v, dict):
                        ep["params"].append({
                            "name": text_of(v.get("name") or v.get("key")),
                            "loc": text_of(v.get("in")) or "query",
                            "required": bool(v.get("required")),
                            "type": text_of(v.get("type")) or "string",
                            "desc": text_of(v.get("description")),
                            "example": v.get("value") or v.get("example")})
                    elif isinstance(v, str):
                        ep["params"].append({"name": v, "loc": "query", "required": False,
                                             "type": "string", "desc": "", "example": None})
        for hkey in ("headers", "header"):
            val = node.get(hkey)
            if isinstance(val, dict):
                for k, v in val.items():
                    ep["headers"].append({"name": str(k), "value": text_of(v)})
            elif isinstance(val, list):
                for v in val:
                    v = as_dict(v)
                    ep["headers"].append({"name": text_of(v.get("name") or v.get("key")),
                                          "value": text_of(v.get("value"))})
        for bkey in ("body", "data", "payload", "requestBody", "request"):
            if bkey in node and node[bkey] not in (None, "", {}, []):
                ep["body_type"] = bkey
                try:
                    ep["body_example"] = json.dumps(node[bkey], indent=2, default=str)
                except Exception:
                    ep["body_example"] = text_of(node[bkey])
                break
        if node.get("auth") or node.get("authorization") or node.get("security"):
            ep["auth"] = text_of(node.get("auth") or node.get("authorization")
                                 or node.get("security"))[:200]
        found[key] = ep

    def walk(node, trail, depth=0):
        if depth > 25:
            return
        if isinstance(node, dict):
            method = None
            for mk in ("method", "httpMethod", "verb", "type", "requestMethod"):
                cand = text_of(node.get(mk)).lower()
                if cand in HTTP_METHODS:
                    method = cand
                    break
            target = None
            for uk in ("url", "path", "endpoint", "uri", "route", "href", "link"):
                cand = node.get(uk)
                if isinstance(cand, dict):
                    cand = cand.get("raw") or cand.get("url")
                cand = text_of(cand)
                if cand and (PATH_RE.match(cand) or URL_RE.match(cand)):
                    target = cand
                    break
            if target:
                record(method or "GET", target, node, trail)
            for key, val in node.items():
                m = METHOD_PREFIX_RE.match(str(key))
                if m:
                    record(m.group(1), m.group(2), val if isinstance(val, dict) else {}, trail)
                elif (PATH_RE.match(str(key)) and isinstance(val, dict)
                      and any(k.lower() in HTTP_METHODS for k in val)):
                    for mk, mv in val.items():
                        if mk.lower() in HTTP_METHODS:
                            record(mk, str(key), mv, trail)
                elif PATH_RE.match(str(key)) and len(str(key)) > 1:
                    record("GET", str(key), val if isinstance(val, dict) else {},
                           trail, weak=True)
                walk(val, trail + [str(key)], depth + 1)
        elif isinstance(node, list):
            for item in node:
                walk(item, trail, depth + 1)
        elif isinstance(node, str):
            m = METHOD_PREFIX_RE.match(node)
            if m and (PATH_RE.match(m.group(2)) or URL_RE.match(m.group(2))):
                record(m.group(1), m.group(2), {}, trail)
            elif (PATH_RE.match(node) and len(node) > 3 and "/" in node[1:]
                  and not node.endswith((".png", ".jpg", ".css", ".svg", ".ico"))):
                record("GET", node, {}, trail, weak=True)

    walk(doc, [])
    second_pass[0] = True
    for args in pending_weak:
        record(*args, weak=True)
    return list(found.values()), "Heuristic scan", sorted(servers)

def load_endpoints(doc):
    if isinstance(doc, dict):
        if doc.get("openapi") or doc.get("swagger") or (
                isinstance(doc.get("paths"), dict) and doc.get("info")):
            eps, title, servers = parse_openapi(doc)
            if eps:
                return eps, title, servers, eps[0]["source"]
        if doc.get("item") is not None and as_dict(doc.get("info")).get("schema", "") or \
                ("item" in doc and "info" in doc):
            eps, title, servers = parse_postman(doc)
            if eps:
                return eps, title, servers, "Postman collection"
        if isinstance(doc.get("log"), dict) and doc["log"].get("entries"):
            eps, title, servers = parse_har(doc)
            if eps:
                return eps, title, servers, "HAR capture"
    eps, title, servers = parse_generic(doc)
    return eps, title, servers, "unknown format (heuristic scan)"

def build_url(ep, base_override=""):
    base = (base_override or ep.get("server") or "").rstrip("/")
    path = ep["path"]
    for prm in ep["params"]:
        if prm["loc"] == "path":
            sample = prm.get("example")
            sample = str(sample) if sample not in (None, "") else "<%s>" % prm["name"]
            path = path.replace("{%s}" % prm["name"], sample)
            path = re.sub(r":%s(?![A-Za-z0-9_])" % re.escape(prm["name"]), sample, path)
    query = []
    for prm in ep["params"]:
        if prm["loc"] == "query":
            val = prm.get("example")
            val = str(val) if val not in (None, "") else "<%s>" % prm["name"]
            query.append("%s=%s" % (prm["name"], val))
    url = base + path
    if query:
        url += ("&" if "?" in url else "?") + "&".join(query)
    return url

def build_curl(ep, base_override=""):
    lines = ["curl -i -sS -X %s '%s'" % (ep["method"], build_url(ep, base_override))]
    have = set()
    for h in ep["headers"]:
        if not h["name"]:
            continue
        have.add(h["name"].lower())
        lines.append("  -H '%s: %s'" % (h["name"], h["value"] or "<value>"))
    for prm in ep["params"]:
        if prm["loc"] in ("header",) and prm["name"].lower() not in have:
            have.add(prm["name"].lower())
            val = prm.get("example") or "<%s>" % prm["name"]
            lines.append("  -H '%s: %s'" % (prm["name"], val))
        if prm["loc"] == "cookie":
            lines.append("  -b '%s=%s'" % (prm["name"], prm.get("example") or "<value>"))
    if ep["auth"] and "authorization" not in have:
        m = re.search(r"apiKey in (\w+) named (\S+?)\)", ep["auth"])
        if m and m.group(1) == "header":
            lines.append("  -H '%s: <api-key>'" % m.group(2))
        elif m and m.group(1) == "cookie":
            lines.append("  -b '%s=<api-key>'" % m.group(2))
        elif m and m.group(1) == "query":
            sep = "&" if "?" in lines[0] else "?"
            lines[0] = lines[0][:-1] + "%s%s=<api-key>'" % (sep, m.group(2))
        elif "basic" in ep["auth"].lower():
            lines.append("  -u '<user>:<pass>'")
        else:
            lines.append("  -H 'Authorization: <token>'")
    if ep["body_example"]:
        ctype = ep["body_type"].split(" ")[0] or "application/json"
        if "/" not in ctype:
            ctype = "application/json"
        if "multipart" in ctype:
            try:
                fields = json.loads(ep["body_example"])
            except Exception:
                fields = {}
            if not isinstance(fields, dict) or not fields:
                fields = {}
                for pair in ep["body_example"].split("&"):
                    if "=" in pair:
                        k, _, v = pair.partition("=")
                        fields[k] = v or "<value>"
                for row in ep["body_schema"].splitlines():
                    bits = row.split()
                    if len(bits) >= 2 and bits[1] == "file":
                        fields[bits[0]] = "<binary>"
            if isinstance(fields, dict) and fields:
                for name, val in fields.items():
                    if str(val) == "<binary>":
                        lines.append("  -F '%s=@/path/to/file'" % name)
                    else:
                        lines.append("  -F '%s=%s'" % (name, str(val)[:80]))
                return " \\\n".join(lines)
        if "content-type" not in have:
            lines.append("  -H 'Content-Type: %s'" % ctype)
        body = ep["body_example"]
        if len(body) > 4000:
            body = body[:4000] + "\n...truncated..."
        body = body.replace("'", "'\\''")
        lines.append("  --data '%s'" % body)
    return " \\\n".join(lines)

def render_details(ep, base_override=""):
    out = []
    out.append(("method", ep["method"]))
    out.append(("path", "  " + ep["path"] + "\n"))
    if ep.get("deprecated"):
        out.append(("warn", "  deprecated\n"))
    if ep["summary"]:
        out.append(("summary", ep["summary"] + "\n"))
    out.append(("gap", "\n"))
    def meta(label, value):
        out.append(("metakey", "%-9s" % label))
        out.append(("metaval", value + "\n"))
    meta("url", build_url(ep, base_override) or ep["path"])
    meta("source", ep["source"])
    if ep["tags"]:
        meta("group", " / ".join(ep["tags"]))
    out.append(("gap", "\n"))

    if ep["description"]:
        out.append(("h", "Description\n"))
        out.append(("plain", ep["description"].strip() + "\n"))
        out.append(("gap", "\n"))
    out.append(("h", "Authentication\n"))
    if ep["auth"]:
        out.append(("plain", ep["auth"] + "\n"))
    else:
        out.append(("warn", "none declared for this operation\n"))
    out.append(("gap", "\n"))
    if ep["params"]:
        out.append(("h", "Parameters\n"))
        for loc in ("path", "query", "header", "cookie", "formData", "body"):
            group = [p for p in ep["params"] if p["loc"] == loc]
            if not group:
                continue
            out.append(("sub", "in " + loc + "\n"))
            for p in group:
                out.append(("pname", "%-24s" % p["name"]))
                out.append(("ptype", "%-11s" % (p["type"] or "-")))
                out.append(("req" if p["required"] else "opt",
                            "required  " if p["required"] else "optional  "))
                if p.get("example") not in (None, ""):
                    out.append(("dim", "e.g. " + str(p["example"])[:44]))
                out.append(("plain", "\n"))
                if p.get("desc"):
                    out.append(("desc", "    " + p["desc"].splitlines()[0][:100] + "\n"))
        other = [p for p in ep["params"] if p["loc"] not in
                 ("path", "query", "header", "cookie", "formData", "body")]
        for p in other:
            out.append(("pname", "%-24s" % p["name"]))
            out.append(("ptype", "%-11s" % (p["type"] or "-")))
            out.append(("dim", "in " + p["loc"] + "\n"))
        out.append(("gap", "\n"))
    if ep["headers"]:
        out.append(("h", "Headers\n"))
        for h in ep["headers"]:
            out.append(("pname", "%-28s" % h["name"]))
            out.append(("plain", h["value"][:70] + "\n"))
        out.append(("gap", "\n"))
    if ep["body_type"] or ep["body_example"] or ep["body_schema"]:
        out.append(("h", "Request body\n"))
        if ep["body_type"]:
            out.append(("sub", ep["body_type"] + "\n"))
        if ep["body_schema"]:
            out.append(("plain", ep["body_schema"] + "\n"))
        if ep["body_example"]:
            out.append(("dim", "sample\n"))
            out.append(("code", ep["body_example"][:6000] + "\n"))
        out.append(("gap", "\n"))
    if ep["responses"]:
        out.append(("h", "Responses\n"))
        for r in ep["responses"]:
            code = r["code"] or "?"
            klass = ("resp2" if code.startswith("2") else
                     "resp3" if code.startswith("3") else
                     "resp4" if code.startswith("4") else
                     "resp5" if code.startswith("5") else "sub")
            out.append((klass, " " + code + " "))
            out.append(("plain", "  " + r["desc"] + "\n"))
            if r["body"]:
                out.append(("dim", "    " + r["body"][:2500] + "\n"))
        out.append(("gap", "\n"))
    notes = flag_notes(ep)
    if notes:
        out.append(("h", "Worth a look\n"))
        for n in notes:
            out.append(("flagdot", "  \u25aa  "))
            out.append(("flag", (n[:1].upper() + n[1:]) + "\n"))
        out.append(("gap", "\n"))
    out.append(("h", "cURL\n"))
    out.append(("code", build_curl(ep, base_override) + "\n"))
    return out

def render_markdown(endpoints, title, base_override=""):
    lines = ["# %s" % title, "", "%d endpoints." % len(endpoints), ""]
    for ep in sorted(endpoints, key=lambda e: (e["path"], e["method"])):
        lines.append("## `%s %s`" % (ep["method"], ep["path"]))
        if ep["summary"]:
            lines.append("")
            lines.append(ep["summary"])
        lines.append("")
        lines.append("- URL: `%s`" % build_url(ep, base_override))
        lines.append("- Auth: %s" % (ep["auth"] or "not declared"))
        if ep["tags"]:
            lines.append("- Group: %s" % " / ".join(ep["tags"]))
        if ep["params"]:
            lines.append("")
            lines.append("| Param | In | Required | Type |")
            lines.append("|---|---|---|---|")
            for p in ep["params"]:
                lines.append("| `%s` | %s | %s | %s |" % (
                    p["name"], p["loc"], "yes" if p["required"] else "no", p["type"]))
        if ep["body_example"]:
            lines.append("")
            lines.append("Body (%s):" % (ep["body_type"] or "raw"))
            lines.append("")
            lines.append("```")
            lines.append(ep["body_example"][:4000])
            lines.append("```")
        if ep["responses"]:
            lines.append("")
            lines.append("Responses: " + ", ".join(
                "%s %s" % (r["code"], r["desc"]) for r in ep["responses"])[:400])
        notes = flag_notes(ep)
        if notes:
            lines.append("")
            lines.append("Worth a look: " + ", ".join(notes))
        lines.append("")
        lines.append("```bash")
        lines.append(build_curl(ep, base_override))
        lines.append("```")
        lines.append("")
    return "\n".join(lines)

class FilePicker(tk.Toplevel):
    def __init__(self, master, title="Open", mode="open", filetypes=None,
                 initialdir=None, initialfile="", theme=None, uifam="TkDefaultFont"):
        super().__init__(master)
        self.result = None
        self.mode = mode
        self.theme = theme or {}
        self.uifam = uifam
        self.filetypes = filetypes or [("All files", "*")]
        self.cwd = os.path.abspath(initialdir or os.getcwd())
        self.title(title)
        self.transient(master)
        self.configure(bg=self.theme.get("bg", "#1a1724"))
        self.geometry("760x540")
        self.minsize(560, 400)
        self.ft_var = tk.StringVar(value=self.filetypes[0][0])
        self.name_var = tk.StringVar(value=initialfile)
        self.path_var = tk.StringVar(value=self.cwd)
        self._build()
        self._populate()
        self.grab_set()
        self.bind("<Escape>", lambda e: self._cancel())
        self.protocol("WM_DELETE_WINDOW", self._cancel)
        self.update_idletasks()
        self._center(master)
        self.wait_window(self)

    def _center(self, master):
        try:
            x = master.winfo_rootx() + (master.winfo_width() - self.winfo_width()) // 2
            y = master.winfo_rooty() + (master.winfo_height() - self.winfo_height()) // 3
            self.geometry("+%d+%d" % (max(x, 0), max(y, 0)))
        except Exception:
            pass

    def _patterns(self):
        for lab, spec in self.filetypes:
            if lab == self.ft_var.get():
                return spec.split()
        return ["*"]

    def _match(self, fname):
        pats = self._patterns()
        if "*" in pats or not pats:
            return True
        low = fname.lower()
        return any(fnmatch.fnmatch(low, p.lower()) for p in pats)

    def _build(self):
        pad = 14
        top = ttk.Frame(self, style="TFrame", padding=(pad, pad, pad, 6))
        top.pack(fill="x")
        ttk.Button(top, text="\u2191  Up", style="Ghost.TButton",
                   command=self._up).pack(side="left")
        ttk.Label(top, textvariable=self.path_var, style="Dim.TLabel").pack(
            side="left", padx=(12, 0))
        mid = ttk.Frame(self, style="Card.TFrame", padding=1)
        mid.pack(fill="both", expand=True, padx=pad, pady=6)
        self.tree = ttk.Treeview(mid, columns=("size",), show="tree headings",
                                 selectmode="browse")
        self.tree.heading("#0", text="  NAME")
        self.tree.heading("size", text="SIZE")
        self.tree.column("#0", width=520, stretch=True)
        self.tree.column("size", width=110, stretch=False, anchor="e")
        sb = ttk.Scrollbar(mid, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.tree.bind("<Double-1>", lambda e: self._activate())
        self.tree.bind("<Return>", lambda e: self._activate())
        self.tree.bind("<BackSpace>", lambda e: self._up())
        self.tree.bind("<<TreeviewSelect>>", lambda e: self._on_select())
        t = self.theme
        self.tree.tag_configure("dir", foreground=t.get("fg", "#d4cfc8"),
                                font=(self.uifam, 10, "bold"))
        self.tree.tag_configure("file", foreground=t.get("fg", "#e7e7ec"),
                                font=(self.uifam, 10))
        bot = ttk.Frame(self, style="TFrame", padding=(pad, 6, pad, pad))
        bot.pack(fill="x")
        col = 0
        if self.mode == "save":
            ttk.Label(bot, text="FILE NAME", style="Micro.TLabel").grid(
                row=0, column=col, sticky="w"); col += 1
            e = ttk.Entry(bot, textvariable=self.name_var, width=30)
            e.grid(row=0, column=col, sticky="ew", padx=(8, 14)); col += 1
            e.bind("<Return>", lambda ev: self._accept())
            e.focus_set()
        ttk.Label(bot, text="TYPE", style="Micro.TLabel").grid(
            row=0, column=col, sticky="w"); col += 1
        ftc = ttk.Combobox(bot, textvariable=self.ft_var, state="readonly",
                           width=16, values=[l for l, _ in self.filetypes])
        ftc.grid(row=0, column=col, padx=(8, 14)); col += 1
        ftc.bind("<<ComboboxSelected>>", lambda e: self._populate())
        ttk.Button(bot, text="Cancel", command=self._cancel).grid(
            row=0, column=col, padx=(0, 8)); col += 1
        ttk.Button(bot, text=("Save" if self.mode == "save" else "Open"),
                   style="Accent.TButton", command=self._accept).grid(row=0, column=col)
        bot.columnconfigure(1, weight=1)

    @staticmethod
    def _fmt_size(n):
        size = float(n)
        for unit in ("B", "KB", "MB", "GB"):
            if size < 1024:
                return "%d %s" % (int(size), unit) if unit == "B" else "%.1f %s" % (size, unit)
            size /= 1024
        return "%.1f TB" % size

    def _populate(self):
        self.tree.delete(*self.tree.get_children())
        self.path_var.set(self.cwd)
        try:
            entries = os.listdir(self.cwd)
        except OSError:
            entries = []
        dirs, files = [], []
        for name in entries:
            if name.startswith("."):
                continue
            full = os.path.join(self.cwd, name)
            if os.path.isdir(full):
                dirs.append(name)
            elif self._match(name):
                files.append(name)
        for name in sorted(dirs, key=str.lower):
            self.tree.insert("", "end", iid="d:" + name, text="  " + name + "/",
                             values=("",), tags=("dir",))
        for name in sorted(files, key=str.lower):
            try:
                sz = self._fmt_size(os.path.getsize(os.path.join(self.cwd, name)))
            except OSError:
                sz = ""
            self.tree.insert("", "end", iid="f:" + name, text="  " + name,
                             values=(sz,), tags=("file",))

    def _sel(self):
        s = self.tree.selection()
        return s[0] if s else None

    def _on_select(self):
        iid = self._sel()
        if iid and iid.startswith("f:"):
            self.name_var.set(iid[2:])

    def _activate(self):
        iid = self._sel()
        if not iid:
            return
        if iid.startswith("d:"):
            self.cwd = os.path.join(self.cwd, iid[2:])
            self._populate()
        else:
            self._accept()

    def _up(self):
        parent = os.path.dirname(self.cwd.rstrip(os.sep)) or os.sep
        if parent and parent != self.cwd:
            self.cwd = parent
            self._populate()

    def _accept(self):
        if self.mode == "save":
            name = self.name_var.get().strip()
            if not name:
                return
            self.result = os.path.join(self.cwd, name)
            self.destroy()
            return
        iid = self._sel()
        if iid and iid.startswith("f:"):
            self.result = os.path.join(self.cwd, iid[2:])
            self.destroy()
        elif iid and iid.startswith("d:"):
            self._activate()

    def _cancel(self):
        self.result = None
        self.destroy()

import tkinter.font as tkfont

class EndpointList(tk.Frame):
    GROUP_H = 36
    ROW_H = 44
    TOP_PAD = 6
    BOT_PAD = 10

    def __init__(self, master, on_select):
        super().__init__(master)
        self.on_select = on_select
        self.canvas = tk.Canvas(self, highlightthickness=0, borderwidth=0,
                                takefocus=True)
        self.vsb = ttk.Scrollbar(self, orient="vertical",
                                 command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.vsb.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.vsb.pack(side="right", fill="y")

        self.groups = []       # [(name, [ep, ...]), ...]
        self.items = []        # flat drawables with geometry
        self.ep_items = []      # indices into self.items that are selectable
        self.sel = None
        self.hover = None
        self.total_h = 0
        self.theme = THEMES["dark"]
        self.mcolors = METHOD_COLORS_DARK
        self.mono = ("DejaVu Sans Mono", 10)
        self.ui_family = "DejaVu Sans"

        self.canvas.bind("<Configure>", lambda e: self._redraw())
        self.canvas.bind("<Motion>", self._on_motion)
        self.canvas.bind("<Leave>", lambda e: self._set_hover(None))
        self.canvas.bind("<Button-1>", self._on_click)
        self.canvas.bind("<MouseWheel>", self._on_wheel)          # win / mac
        self.canvas.bind("<Button-4>", lambda e: self._scroll(-3))  # x11 up
        self.canvas.bind("<Button-5>", lambda e: self._scroll(3))   # x11 down
        self.canvas.bind("<Up>", lambda e: self._step(-1))
        self.canvas.bind("<Down>", lambda e: self._step(1))
    def set_theme(self, theme, mcolors, mono, ui_family):
        self.theme = theme
        self.mcolors = mcolors
        self.mono = mono
        self.ui_family = ui_family
        self._badge_font = tkfont.Font(family=ui_family, size=9, weight="bold")
        self._path_font = tkfont.Font(family=mono[0], size=11)
        self._sum_font = tkfont.Font(family=ui_family, size=10)
        self._grp_font = tkfont.Font(family=ui_family, size=9, weight="bold")
        self.canvas.configure(background=theme["panel"])
        self.configure(background=theme["border"])
        self._redraw()
    def set_data(self, groups):
        self.groups = groups
        self.sel = None
        self.hover = None
        self._layout()
        self.canvas.yview_moveto(0)
        self._redraw()

    def _layout(self):
        self.items = []
        self.ep_items = []
        y = self.TOP_PAD
        for name, eps in self.groups:
            self.items.append({"kind": "group", "name": name, "n": len(eps),
                               "y0": y, "y1": y + self.GROUP_H})
            y += self.GROUP_H
            for ep in eps:
                idx = len(self.items)
                self.items.append({"kind": "ep", "ep": ep,
                                   "y0": y, "y1": y + self.ROW_H})
                self.ep_items.append(idx)
                y += self.ROW_H
            y += 6
        self.total_h = y + self.BOT_PAD
        self.canvas.configure(scrollregion=(0, 0, 1, self.total_h))
    @staticmethod
    def _round_rect(cv, x0, y0, x1, y1, r, **kw):
        r = min(r, (x1 - x0) / 2, (y1 - y0) / 2)
        pts = [x0 + r, y0, x1 - r, y0, x1, y0, x1, y0 + r, x1, y1 - r, x1, y1,
               x1 - r, y1, x0 + r, y1, x0, y1, x0, y1 - r, x0, y0 + r, x0, y0]
        return cv.create_polygon(pts, smooth=True, **kw)

    def _redraw(self):
        cv = self.canvas
        cv.delete("all")
        if not getattr(self, "_path_font", None):
            return
        t = self.theme
        w = cv.winfo_width() or 380
        for i, it in enumerate(self.items):
            y0, y1 = it["y0"], it["y1"]
            if it["kind"] == "group":
                cv.create_text(18, (y0 + y1) / 2 - 1, anchor="w",
                               text=it["name"].upper(), fill=t["faint"],
                               font=self._grp_font)
                cv.create_text(18 + self._grp_font.measure(it["name"].upper()) + 10,
                               (y0 + y1) / 2 - 1, anchor="w",
                               text=str(it["n"]), fill=t["faint"],
                               font=self._grp_font)
                cv.create_line(18, y1 - 4, w - 14, y1 - 4, fill=t["border"])
                continue
            ep = it["ep"]
            selected = (i == self.sel)
            hovered = (i == self.hover) and not selected
            if selected:
                self._round_rect(cv, 10, y0 + 3, w - 10, y1 - 3, 9,
                                 fill=t["sel"], outline="")
                cv.create_rectangle(10, y0 + 8, 13, y1 - 8, fill=t["accent"],
                                    outline="")
            elif hovered:
                self._round_rect(cv, 10, y0 + 3, w - 10, y1 - 3, 9,
                                 fill=t["hover"], outline="")
            m = ep["method"]
            col = self.mcolors.get(m, t["faint"])
            tw = self._badge_font.measure(m)
            bx0, bx1 = 22, 22 + max(46, tw + 18)
            by0 = (y0 + y1) / 2 - 10
            self._round_rect(cv, bx0, by0, bx1, by0 + 20, 6, fill=col, outline="")
            cv.create_text((bx0 + bx1) / 2, by0 + 10, text=m, fill="#ffffff",
                           font=self._badge_font)
            tx = bx1 + 14
            fg = t["sel_fg"] if selected else t["fg"]
            cv.create_text(tx, (y0 + y1) / 2, anchor="w", text=ep["path"],
                           fill=fg, font=self._path_font)
            if ep["summary"]:
                px = tx + self._path_font.measure(ep["path"]) + 14
                avail = (w - 22) - px
                if avail > 40:
                    s = ep["summary"]
                    while s and self._sum_font.measure(s) > avail:
                        s = s[:-1]
                    if s != ep["summary"]:
                        s = s[:-1] + "\u2026"
                    cv.create_text(px, (y0 + y1) / 2, anchor="w", text=s,
                                   fill=t["faint"], font=self._sum_font)
    def _at(self, ev_y):
        y = self.canvas.canvasy(ev_y)
        for i, it in enumerate(self.items):
            if it["kind"] == "ep" and it["y0"] <= y < it["y1"]:
                return i
        return None

    def _on_motion(self, ev):
        self._set_hover(self._at(ev.y))

    def _set_hover(self, i):
        if i != self.hover:
            self.hover = i
            self._redraw()

    def _on_click(self, ev):
        self.canvas.focus_set()
        i = self._at(ev.y)
        if i is not None:
            self.select(i)

    def select(self, i, notify=True):
        if i is None or i >= len(self.items):
            return
        self.sel = i
        self._ensure_visible(i)
        self._redraw()
        if notify and self.on_select:
            self.on_select(self.items[i]["ep"])

    def select_first(self):
        if self.ep_items:
            self.select(self.ep_items[0])

    def current_ep(self):
        if self.sel is not None and self.sel < len(self.items):
            it = self.items[self.sel]
            if it["kind"] == "ep":
                return it["ep"]
        return None

    def _step(self, d):
        if not self.ep_items:
            return "break"
        if self.sel in self.ep_items:
            pos = self.ep_items.index(self.sel)
            pos = max(0, min(len(self.ep_items) - 1, pos + d))
        else:
            pos = 0
        self.select(self.ep_items[pos])
        return "break"

    def _ensure_visible(self, i):
        if self.total_h <= 0:
            return
        it = self.items[i]
        top = self.canvas.canvasy(0)
        h = self.canvas.winfo_height()
        bottom = top + h
        if it["y0"] < top:
            self.canvas.yview_moveto(max(0, it["y0"] - 6) / self.total_h)
        elif it["y1"] > bottom:
            self.canvas.yview_moveto(max(0, it["y1"] - h + 6) / self.total_h)

    def _scroll(self, units):
        self.canvas.yview_scroll(units, "units")

    def _on_wheel(self, ev):
        self.canvas.yview_scroll(-1 * (ev.delta // 120 or (1 if ev.delta < 0 else -1)),
                                 "units")

class BloodlessAPI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("%s %s" % (APP_NAME, VERSION))
        self.geometry("1320x860")
        self.minsize(980, 620)
        try:
            icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app_icon.png")
            self._icon = tk.PhotoImage(file=icon_path)
            self.iconphoto(True, self._icon)
        except Exception:
            pass
        self.endpoints = []
        self.visible = []
        self.doc_title = ""
        self.servers = []
        self.fmt = ""
        self.current_path = ""
        self.filter_var = tk.StringVar()
        self.method_var = tk.StringVar(value="ALL")
        self.base_var = tk.StringVar()
        self.status_var = tk.StringVar(value="Open or paste JSON to begin.")
        self.theme_name = "dark"
        self._build_ui()
        self.filter_var.trace_add("write", lambda *_: self.refresh_tree())
        self.method_var.trace_add("write", lambda *_: self.refresh_tree())
        self.base_var.trace_add("write", lambda *_: self.show_current())
        if len(sys.argv) > 1 and os.path.isfile(sys.argv[1]):
            self.load_file(sys.argv[1])

    def _build_ui(self):
        mono = ("Consolas" if sys.platform.startswith("win")
                else "Menlo" if sys.platform == "darwin"
                else "DejaVu Sans Mono")
        import tkinter.font as tkfont
        fams = set(tkfont.families())
        if "Fira Code" in fams:
            mono = "Fira Code"
        self.mono = (mono, 10)
        ui_fam = next((f for f in ("Inter", "Segoe UI", "SF Pro Text",
                                   "Helvetica Neue", "Helvetica", "Arial")
                       if f in fams), "Helvetica")
        self.ui_fam = ui_fam
        self.ui_font = (ui_fam, 10)
        self.ui_bold = (ui_fam, 10, "bold")
        self.style = ttk.Style(self)
        self._seps = []
        header = ttk.Frame(self, style="TFrame", padding=(24, 16, 24, 14))
        header.pack(fill="x")
        brand = ttk.Frame(header, style="TFrame")
        brand.pack(side="left")
        self._brandbar = tk.Frame(brand, width=4, height=26)
        self._brandbar.pack(side="left", padx=(0, 14))
        self._brandbar.pack_propagate(False)
        ttk.Label(brand, text=APP_NAME, style="Title.TLabel").pack(side="left")
        ttk.Label(brand, text="v" + VERSION, style="Ver.TLabel").pack(
            side="left", padx=(10, 0), pady=(6, 0))
        ttk.Label(header, text="API surface mapper", style="Tag.TLabel").pack(
            side="left", padx=(18, 0), pady=(4, 0))
        self.theme_btn = ttk.Button(header, text="Light mode",
                                    command=self.toggle_theme, style="Ghost.TButton")
        self.theme_btn.pack(side="right")

        self._sep(self)
        bar = ttk.Frame(self, style="TFrame", padding=(24, 12))
        bar.pack(fill="x")
        ttk.Button(bar, text="Open JSON", command=self.pick_file,
                   style="Accent.TButton").pack(side="left")
        ttk.Button(bar, text="Paste JSON", command=self.paste_json,
                   style="Ghost.TButton").pack(side="left", padx=(10, 0))
        ttk.Separator(bar, orient="vertical").pack(side="left", fill="y",
                                                   padx=16, pady=3)
        ttk.Button(bar, text="Export Markdown", command=self.export_md,
                   style="Ghost.TButton").pack(side="left")
        ttk.Button(bar, text="Export cURL", command=self.export_curl,
                   style="Ghost.TButton").pack(side="left", padx=(8, 0))
        entry = ttk.Entry(bar, textvariable=self.filter_var, width=24,
                          style="Search.TEntry")
        entry.pack(side="right")
        entry.bind("<Escape>", lambda e: self.filter_var.set(""))
        self.filter_entry = entry
        ttk.Label(bar, text="FILTER", style="Micro.TLabel").pack(
            side="right", padx=(0, 8))
        method_cb = ttk.Combobox(bar, textvariable=self.method_var, width=8,
                                 state="readonly",
                                 values=("ALL",) + tuple(m.upper() for m in HTTP_METHODS))
        method_cb.pack(side="right", padx=(0, 18))
        ttk.Label(bar, text="METHOD", style="Micro.TLabel").pack(
            side="right", padx=(0, 8))
        self.base_combo = ttk.Combobox(bar, textvariable=self.base_var, width=26)
        self.base_combo.pack(side="right", padx=(0, 18))
        ttk.Label(bar, text="BASE URL", style="Micro.TLabel").pack(
            side="right", padx=(0, 8))

        self._sep(self)
        body = ttk.Frame(self, style="TFrame", padding=(18, 14))
        body.pack(fill="both", expand=True)
        paned = ttk.PanedWindow(body, orient="horizontal")
        paned.pack(fill="both", expand=True)

        left = ttk.Frame(paned, style="Card.TFrame", padding=1)
        self.list = EndpointList(left, on_select=lambda ep: self.show_current())
        self.list.pack(fill="both", expand=True)
        paned.add(left, weight=2)

        right = ttk.Frame(paned, style="Card.TFrame", padding=1)
        self.text = tk.Text(right, wrap="none", font=self.mono, padx=30, pady=26,
                            borderwidth=0, highlightthickness=0, spacing1=2,
                            spacing3=2, state="disabled", cursor="arrow")
        tsb = ttk.Scrollbar(right, orient="vertical", command=self.text.yview)
        hsb = ttk.Scrollbar(right, orient="horizontal", command=self.text.xview)
        self.text.configure(yscrollcommand=tsb.set, xscrollcommand=hsb.set)
        self.text.grid(row=0, column=0, sticky="nsew")
        tsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        right.rowconfigure(0, weight=1)
        right.columnconfigure(0, weight=1)
        paned.add(right, weight=3)

        self.text.bind("<Control-a>", self._text_select_all)
        self.text.bind("<Control-A>", self._text_select_all)
        self.text.bind("<Control-c>", self._text_copy)
        self.text.bind("<Control-C>", self._text_copy)
        self.text.bind("<Button-3>", self._text_context_menu)
        self.text.bind("<Key>", lambda e: "break")

        self.welcome = ttk.Frame(right, style="Welcome.TFrame", padding=40)
        self._wc_mark = tk.Frame(self.welcome, width=58, height=58)
        self._wc_mark.pack()
        self._wc_mark.pack_propagate(False)
        self._wc_glyph = ttk.Label(self._wc_mark, text="{ }", style="Glyph.TLabel")
        self._wc_glyph.place(relx=0.5, rely=0.5, anchor="center")
        ttk.Label(self.welcome, text=APP_NAME, style="Hero.TLabel").pack(pady=(20, 4))
        self._wc_sub = ttk.Label(self.welcome, text="", style="HeroSub.TLabel",
                                 justify="center")
        self._wc_sub.pack()
        ttk.Label(self.welcome, text="OpenAPI   ·   Swagger   ·   Postman   ·   HAR",
                  style="HeroFaint.TLabel").pack(pady=(18, 0))
        self._wc_btn = ttk.Button(self.welcome, text="Open JSON",
                                  command=self.pick_file, style="Accent.TButton")
        self._wc_btn.pack(pady=(24, 0))
        self._wc_paste = ttk.Button(self.welcome, text="Paste JSON",
                                    command=self.paste_json, style="Ghost.TButton")
        self._wc_paste.pack(pady=(10, 0))

        self._sep(self)
        bottom = ttk.Frame(self, style="TFrame", padding=(22, 11))
        bottom.pack(fill="x")
        ttk.Button(bottom, text="Copy cURL", command=self.copy_curl,
                   style="Ghost.TButton").pack(side="left")
        ttk.Button(bottom, text="Copy URL", command=self.copy_url,
                   style="Ghost.TButton").pack(side="left", padx=(8, 0))
        ttk.Button(bottom, text="Copy details", command=self.copy_details,
                   style="Ghost.TButton").pack(side="left", padx=(8, 0))
        ttk.Label(bottom, textvariable=self.status_var,
                  style="Status.TLabel").pack(side="right")

        self.bind("<Control-o>", lambda e: self.pick_file())
        self.bind("<Control-f>", lambda e: self.filter_entry.focus_set())
        self.bind("<Control-l>", lambda e: self.toggle_theme())
        self.bind("<Control-Shift-V>", lambda e: self.paste_json())
        self.bind("<Control-Shift-v>", lambda e: self.paste_json())

        self.apply_theme(self.theme_name)
        self.set_welcome("Open or paste JSON to map its API surface.")

    def _sep(self, parent):
        s = tk.Frame(parent, height=1)
        s.pack(fill="x")
        self._seps.append(s)

    def set_welcome(self, message, show_button=True):
        self._wc_sub.configure(text=message)
        if show_button:
            self._wc_btn.pack(pady=(24, 0))
            self._wc_paste.pack(pady=(10, 0))
        else:
            self._wc_btn.pack_forget()
            self._wc_paste.pack_forget()
        self.welcome.place(relx=0.5, rely=0.5, anchor="center")
        self.welcome.lift()

    def hide_welcome(self):
        self.welcome.place_forget()

    def _text_select_all(self, event=None):
        self.text.configure(state="normal")
        self.text.tag_add("sel", "1.0", "end-1c")
        self.text.mark_set("insert", "1.0")
        self.text.see("insert")
        self.text.configure(state="disabled")
        return "break"

    def _text_copy(self, event=None):
        try:
            sel = self.text.get("sel.first", "sel.last")
            self.clipboard_clear()
            self.clipboard_append(sel)
        except tk.TclError:
            pass
        return "break"

    def _text_context_menu(self, event):
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label="Select All", command=lambda: self._text_select_all())
        menu.add_command(label="Copy", command=lambda: self._text_copy())
        menu.add_separator()
        menu.add_command(label="Paste JSON (load spec)", command=self.paste_json)
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _select_first(self):
        self.list.select_first()

    @staticmethod
    def _ideal_text(hexcol):
        h = hexcol.lstrip("#")
        r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
        def lin(c):
            return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
        lum = 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)
        return "#10131c" if lum > 0.55 else "#ffffff"

    def _theme_dialogs(self, t):
        o = self.option_add
        o("*background", t["panel"])
        o("*foreground", t["fg"])
        o("*Entry.background", t["elevated"])
        o("*Entry.foreground", t["fg"])
        o("*Entry.insertBackground", t["fg"])
        o("*Entry.highlightColor", t["accent"])
        o("*Entry.highlightBackground", t["border"])
        o("*Listbox.background", t["panel"])
        o("*Listbox.foreground", t["fg"])
        o("*Listbox.selectBackground", t["accent"])
        o("*Listbox.selectForeground", t["accent_fg"])
        o("*Button.background", t["elevated"])
        o("*Button.foreground", t["fg"])
        o("*Button.activeBackground", t["hover"])
        o("*Button.activeForeground", t["fg"])
        o("*Button.highlightBackground", t["panel"])
        o("*Label.background", t["panel"])
        o("*Label.foreground", t["fg"])
        o("*Frame.background", t["panel"])
        o("*Toplevel.background", t["panel"])
        o("*Menu.background", t["panel"])
        o("*Menu.foreground", t["fg"])
        o("*Menu.activeBackground", t["accent"])
        o("*Menu.activeForeground", t["accent_fg"])
        o("*Scrollbar.background", t["elevated"])
        o("*Scrollbar.troughColor", t["bg"])
        o("*Scrollbar.activeBackground", t["hover"])
        o("*Canvas.background", t["panel"])
        o("*IconList.background", t["panel"])
        o("*IconList.foreground", t["fg"])
        o("*IconList.selectBackground", t["accent"])
        o("*IconList.selectForeground", t["accent_fg"])

    def toggle_theme(self):
        self.apply_theme("light" if self.theme_name == "dark" else "dark")

    def apply_theme(self, name):
        t = THEMES[name]
        self.theme_name = name
        self.configure(bg=t["bg"])
        self._style_ttk(t)
        self._theme_dialogs(t)
        for s in self._seps:
            s.configure(bg=t["border"])
        self._brandbar.configure(bg=t["accent"])
        self._wc_mark.configure(bg=t["accent_soft"])
        self.text.configure(background=t["panel"], foreground=t["fg"],
                            insertbackground=t["fg"], selectbackground=t["sel"],
                            selectforeground=t["sel_fg"],
                            inactiveselectbackground=t["sel"])
        self._style_text_tags(t, name)
        colors = METHOD_COLORS_DARK if name == "dark" else METHOD_COLORS
        self.list.set_theme(t, colors, self.mono, self.ui_fam)
        self.theme_btn.configure(text="Light mode" if name == "dark" else "Dark mode")

    def _style_ttk(self, t):
        st = self.style
        try:
            st.theme_use("clam")
        except tk.TclError:
            pass
        st.configure(".", background=t["bg"], foreground=t["fg"],
                     fieldbackground=t["elevated"], bordercolor=t["border"],
                     lightcolor=t["border"], darkcolor=t["border"], font=self.ui_font)
        st.configure("TFrame", background=t["bg"])
        st.configure("Card.TFrame", background=t["border"])
        st.configure("Welcome.TFrame", background=t["panel"])
        st.configure("TLabel", background=t["bg"], foreground=t["fg"])
        st.configure("Dim.TLabel", background=t["bg"], foreground=t["dim"])
        st.configure("Micro.TLabel", background=t["bg"], foreground=t["faint"],
                     font=(self.ui_fam, 8, "bold"))
        st.configure("Title.TLabel", background=t["bg"], foreground=t["fg"],
                     font=(self.ui_fam, 17, "bold"))
        st.configure("Ver.TLabel", background=t["bg"], foreground=t["faint"],
                     font=(self.ui_fam, 9))
        st.configure("Tag.TLabel", background=t["bg"], foreground=t["dim"],
                     font=(self.ui_fam, 10))
        st.configure("Status.TLabel", background=t["bg"], foreground=t["dim"])
        st.configure("Glyph.TLabel", background=t["accent_soft"], foreground=t["accent"],
                     font=(self.mono[0], 17, "bold"))
        st.configure("Hero.TLabel", background=t["panel"], foreground=t["fg"],
                     font=(self.ui_fam, 21, "bold"))
        st.configure("HeroSub.TLabel", background=t["panel"], foreground=t["dim"],
                     font=(self.ui_fam, 11))
        st.configure("HeroFaint.TLabel", background=t["panel"], foreground=t["faint"],
                     font=(self.ui_fam, 10))
        st.configure("TButton", background=t["elevated"], foreground=t["fg"],
                     bordercolor=t["border"], relief="flat", padding=(16, 9),
                     font=self.ui_bold)
        st.map("TButton",
               background=[("pressed", t["border"]), ("active", t["hover"])],
               bordercolor=[("active", t["accent"])],
               foreground=[("disabled", t["faint"])],
               relief=[("pressed", "flat"), ("active", "flat")])
        st.configure("Accent.TButton", background=t["accent"],
                     foreground=t["accent_fg"], bordercolor=t["accent"],
                     padding=(20, 10), font=(self.ui_fam, 10, "bold"))
        st.map("Accent.TButton",
               background=[("pressed", t["accent_press"]), ("active", t["accent_hover"])],
               bordercolor=[("pressed", t["accent_press"]), ("active", t["accent_hover"])],
               foreground=[("pressed", t["accent_fg"]), ("active", t["accent_fg"])],
               relief=[("pressed", "flat"), ("active", "flat")])
        st.configure("Ghost.TButton", background=t["elevated"], foreground=t["dim"],
                     bordercolor=t["border"], padding=(15, 9),
                     font=(self.ui_fam, 10))
        st.map("Ghost.TButton",
               background=[("pressed", t["border"]), ("active", t["hover"])],
               foreground=[("pressed", t["fg"]), ("active", t["fg"])],
               bordercolor=[("pressed", t["accent"]), ("active", t["accent"])],
               relief=[("pressed", "flat"), ("active", "flat")])
        st.configure("TEntry", fieldbackground=t["elevated"], foreground=t["fg"],
                     bordercolor=t["border"], padding=6, insertcolor=t["fg"])
        st.map("TEntry", bordercolor=[("focus", t["accent"])])
        st.configure("Search.TEntry", fieldbackground=t["elevated"], foreground=t["fg"],
                     bordercolor=t["border"], padding=(8, 7), insertcolor=t["fg"])
        st.map("Search.TEntry", bordercolor=[("focus", t["accent"])])
        st.configure("TCombobox", fieldbackground=t["elevated"], background=t["elevated"],
                     foreground=t["fg"], arrowcolor=t["dim"], bordercolor=t["border"],
                     padding=6)
        st.map("TCombobox",
               fieldbackground=[("readonly", t["elevated"])],
               foreground=[("readonly", t["fg"])],
               bordercolor=[("focus", t["accent"])],
               arrowcolor=[("active", t["accent"])])
        self.option_add("*TCombobox*Listbox.background", t["elevated"])
        self.option_add("*TCombobox*Listbox.foreground", t["fg"])
        self.option_add("*TCombobox*Listbox.selectBackground", t["accent"])
        self.option_add("*TCombobox*Listbox.selectForeground", t["accent_fg"])
        st.configure("Treeview", background=t["panel"], fieldbackground=t["panel"],
                     foreground=t["fg"], bordercolor=t["border"], relief="flat",
                     rowheight=27, font=self.ui_font)
        st.map("Treeview",
               background=[("selected", t["accent"])],
               foreground=[("selected", t["accent_fg"])])
        st.configure("Treeview.Heading", background=t["elevated"],
                     foreground=t["dim"], relief="flat", padding=(10, 7),
                     bordercolor=t["border"], font=(self.ui_fam, 9, "bold"))
        st.map("Treeview.Heading",
               background=[("active", t["hover"])],
               foreground=[("active", t["fg"])])
        st.configure("TSeparator", background=t["border"])
        for orient in ("Vertical.TScrollbar", "Horizontal.TScrollbar"):
            st.configure(orient, background=t["border"], troughcolor=t["panel"],
                         bordercolor=t["panel"], arrowcolor=t["faint"], relief="flat",
                         width=12)
            st.map(orient, background=[("active", t["faint"])])
        st.configure("TPanedwindow", background=t["bg"])
        try:
            st.configure("Sash", sashthickness=10, gripcount=0)
        except tk.TclError:
            pass

    def _style_text_tags(self, t, name):
        m = self.mono[0]
        ui = self.ui_fam
        colors = METHOD_COLORS_DARK if name == "dark" else METHOD_COLORS
        for meth, col in colors.items():
            self.text.tag_configure("chip_" + meth, background=col,
                                    foreground="#ffffff",
                                    font=(ui, 10, "bold"), spacing1=2)
        self.text.tag_configure("path", font=(m, 16, "bold"), foreground=t["fg"],
                                spacing1=2, spacing3=2)
        self.text.tag_configure("summary", font=(ui, 12), foreground=t["dim"],
                                lmargin1=2, lmargin2=2, spacing1=4, spacing3=2)
        self.text.tag_configure("metakey", foreground=t["faint"], font=(m, 10))
        self.text.tag_configure("metaval", foreground=t["dim"], font=(m, 10))
        self.text.tag_configure("h", font=(ui, 10, "bold"), foreground=t["accent2"],
                                spacing1=20, spacing3=10)
        self.text.tag_configure("sub", font=(m, 10, "bold"), foreground=t["dim"],
                                spacing1=2)
        self.text.tag_configure("pname", foreground=t["fg"], font=(m, 10))
        self.text.tag_configure("ptype", foreground=t["dim"], font=(m, 10))
        self.text.tag_configure("req", foreground=t["danger"], font=(m, 10, "bold"))
        self.text.tag_configure("opt", foreground=t["faint"], font=(m, 10))
        self.text.tag_configure("desc", foreground=t["faint"], font=(ui, 10),
                                spacing3=2)
        self.text.tag_configure("dim", foreground=t["dim"], font=(m, 10))
        self.text.tag_configure("warn", foreground=t["danger"],
                                font=(ui, 11, "bold"))
        self.text.tag_configure("plain", foreground=t["fg"], font=(m, 10))
        self.text.tag_configure("code", background=t["code_bg"], foreground=t["code_fg"],
                                lmargin1=18, lmargin2=18, rmargin=18,
                                spacing1=10, spacing3=10, font=(m, 10),
                                borderwidth=0)
        self.text.tag_configure("flag", foreground=t["fg"], font=(ui, 12),
                                spacing1=4, spacing3=2)
        self.text.tag_configure("flagdot", foreground=t["accent"], font=(m, 12),
                                spacing1=4)
        self.text.tag_configure("gap", font=(ui, 4))
        for code, col in (("resp2", t["ok"]), ("resp3", "#c47612"),
                          ("resp4", t["accent"]), ("resp5", t["danger"])):
            self.text.tag_configure(code, background=col, foreground="#ffffff",
                                    font=(m, 10, "bold"))

    def pick_file(self):
        path = FilePicker(
            self, title="Open JSON", mode="open",
            filetypes=[("JSON / HAR", "*.json *.har"), ("JSON files", "*.json"),
                       ("HAR files", "*.har"), ("All files", "*")],
            initialdir=getattr(self, "_last_dir", None),
            theme=THEMES[self.theme_name], uifam=self.ui_fam).result
        if path:
            self._last_dir = os.path.dirname(path)
            self.load_file(path)

    def paste_json(self):
        try:
            content = self.clipboard_get()
        except tk.TclError:
            messagebox.showinfo("Clipboard empty", "Nothing on the clipboard to paste.")
            return
        content = content.strip()
        if not content:
            messagebox.showinfo("Clipboard empty", "Nothing on the clipboard to paste.")
            return
        try:
            doc = json.loads(content)
        except json.JSONDecodeError as exc:
            messagebox.showerror("Invalid JSON",
                                 "Clipboard does not contain valid JSON.\n\nLine %d, column %d: %s"
                                 % (exc.lineno, exc.colno, exc.msg))
            return
        self._load_doc(doc, source_label="pasted")

    def load_file(self, path):
        try:
            with open(path, "r", encoding="utf-8-sig", errors="replace") as fh:
                doc = json.load(fh)
        except json.JSONDecodeError as exc:
            messagebox.showerror("Cannot read file",
                                 "This is not valid JSON.\n\nLine %d, column %d: %s"
                                 % (exc.lineno, exc.colno, exc.msg))
            return
        except OSError as exc:
            messagebox.showerror("Cannot read file", str(exc))
            return
        self._load_doc(doc, source_label=path)

    def _load_doc(self, doc, source_label=""):
        try:
            eps, title, servers, fmt = load_endpoints(doc)
        except Exception as exc:
            messagebox.showerror("Cannot parse spec",
                                 "Parsing failed: %s\n\nFalling back to heuristic scan."
                                 % exc)
            eps, title, servers = parse_generic(doc)
            fmt = "heuristic scan"
        self.endpoints = eps
        self.doc_title = title
        self.servers = servers
        self.fmt = fmt
        self.current_path = source_label
        self.base_combo["values"] = servers
        if servers and not self.base_var.get():
            self.base_var.set(servers[0])
        if source_label and source_label != "pasted":
            self.title("%s %s - %s" % (APP_NAME, VERSION, os.path.basename(source_label)))
        else:
            self.title("%s %s - pasted" % (APP_NAME, VERSION))
        self.refresh_tree()
        if not eps:
            self.status_var.set("No endpoints found — read as %s" % fmt)
            self._text_clear()
            self.set_welcome("Nothing endpoint-shaped in this content.\n"
                             "Read as: %s" % fmt, show_button=False)
        else:
            self.hide_welcome()
            self._select_first()
            self.status_var.set("%s   ·   %d endpoints   ·   %s"
                                % (title, len(eps), fmt))

    def matches(self, ep):
        want = self.method_var.get()
        if want != "ALL" and ep["method"] != want:
            return False
        needle = self.filter_var.get().strip().lower()
        if not needle:
            return True
        hay = " ".join([ep["path"], ep["method"], ep["summary"], ep["description"],
                        " ".join(ep["tags"]), ep["auth"], ep["body_example"][:500],
                        " ".join(p["name"] for p in ep["params"])]).lower()
        return all(part in hay for part in needle.split())

    def refresh_tree(self):
        self.visible = [ep for ep in self.endpoints if self.matches(ep)]
        groups = {}
        for ep in self.visible:
            key = ep["tags"][0] if ep["tags"] else (
                ep["path"].strip("/").split("/")[0] or "root")
            groups.setdefault(key, []).append(ep)
        ordered = []
        for group in sorted(groups, key=str.lower):
            eps = sorted(groups[group], key=lambda e: (e["path"], e["method"]))
            ordered.append((group, eps))
        self.list.set_data(ordered)
        if self.endpoints:
            self.status_var.set("%s   ·   showing %d of %d   ·   %s" % (
                self.doc_title, len(self.visible), len(self.endpoints), self.fmt))
            if not self.visible:
                self._text_clear()
                self.set_welcome("No endpoints match this filter.", show_button=False)
            else:
                self.hide_welcome()
                self._select_first()

    def selected(self):
        return self.list.current_ep()

    def _text_clear(self):
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.configure(state="disabled")

    def show_current(self):
        ep = self.selected()
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        if not ep:
            self.text.configure(state="disabled")
            return
        self.hide_welcome()
        for tag, chunk in render_details(ep, self.base_var.get()):
            if tag == "method":
                m = ep["method"]
                self.text.insert("end", " " + m + " ", ("chip_" + m,))
                self.text.insert("end", "  ")
            else:
                self.text.insert("end", chunk, tag)
        self.text.configure(state="disabled")

    def _clip(self, value, label):
        self.clipboard_clear()
        self.clipboard_append(value)
        self.status_var.set(label + " copied to clipboard")

    def copy_curl(self):
        ep = self.selected()
        if ep:
            self._clip(build_curl(ep, self.base_var.get()), "cURL")

    def copy_url(self):
        ep = self.selected()
        if ep:
            self._clip(build_url(ep, self.base_var.get()), "URL")

    def copy_details(self):
        ep = self.selected()
        if ep:
            self._clip("".join(chunk for _, chunk in
                               render_details(ep, self.base_var.get())), "Details")

    def export_md(self):
        if not self.visible:
            messagebox.showinfo("Nothing to export", "Load a file first.")
            return
        path = FilePicker(
            self, title="Export Markdown", mode="save",
            filetypes=[("Markdown", "*.md"), ("All files", "*")],
            initialdir=getattr(self, "_last_dir", None),
            initialfile=(os.path.splitext(os.path.basename(self.current_path or "api"))[0]
                         + "-endpoints.md"),
            theme=THEMES[self.theme_name], uifam=self.ui_fam).result
        if not path:
            return
        if not path.lower().endswith(".md"):
            path += ".md"
        try:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(render_markdown(self.visible, self.doc_title, self.base_var.get()))
            self.status_var.set("Wrote %d endpoints to %s" % (len(self.visible),
                                                              os.path.basename(path)))
        except OSError as exc:
            messagebox.showerror("Cannot write file", str(exc))

    def export_curl(self):
        if not self.visible:
            messagebox.showinfo("Nothing to export", "Load a file first.")
            return
        path = FilePicker(
            self, title="Export cURL", mode="save",
            filetypes=[("Shell script", "*.sh"), ("Text", "*.txt"), ("All files", "*")],
            initialdir=getattr(self, "_last_dir", None),
            initialfile=(os.path.splitext(os.path.basename(self.current_path or "api"))[0]
                         + "-curl.sh"),
            theme=THEMES[self.theme_name], uifam=self.ui_fam).result
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("#!/bin/sh\n# %s - %d endpoints\n# Review before running anything.\n\n"
                         % (self.doc_title, len(self.visible)))
                for ep in sorted(self.visible, key=lambda e: (e["path"], e["method"])):
                    fh.write("# %s %s%s\n" % (ep["method"], ep["path"],
                                              "  - " + ep["summary"] if ep["summary"] else ""))
                    fh.write(build_curl(ep, self.base_var.get()) + "\n\n")
            self.status_var.set("Wrote %d requests to %s" % (len(self.visible),
                                                             os.path.basename(path)))
        except OSError as exc:
            messagebox.showerror("Cannot write file", str(exc))

def main():
    app = BloodlessAPI()
    app.mainloop()

if __name__ == "__main__":
    main()

