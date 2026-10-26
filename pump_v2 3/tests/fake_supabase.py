"""Tiny in-memory stand-in for the Supabase client (select/insert/update/upsert
with eq/neq/gte/lte/in_/order/limit). Lets us test the whole flow offline."""
import copy
import itertools


class Resp:
    def __init__(self, data):
        self.data = data


class FakeDB:
    def __init__(self):
        self.tables = {}
        self._ids = itertools.count(1)
        self.fail_on = {}  # (table, op) -> error message, to simulate failures

    def table(self, name):
        return Query(self, name)


class Query:
    def __init__(self, db, name):
        self.db, self.name = db, name
        self.op, self.payload, self.filters, self.orders, self.n = "select", None, [], [], None

    def select(self, *_):
        self.op = "select"; return self

    def insert(self, p):
        self.op, self.payload = "insert", p; return self

    def update(self, p):
        self.op, self.payload = "update", p; return self

    def upsert(self, p):
        self.op, self.payload = "upsert", p; return self

    def eq(self, c, v): self.filters.append(("eq", c, v)); return self
    def neq(self, c, v): self.filters.append(("neq", c, v)); return self
    def gte(self, c, v): self.filters.append(("gte", c, v)); return self
    def lte(self, c, v): self.filters.append(("lte", c, v)); return self
    def in_(self, c, v): self.filters.append(("in", c, v)); return self

    def order(self, col, desc=False):
        self.orders.append((col, desc)); return self

    def limit(self, n):
        self.n = n; return self

    def _match(self, row):
        for kind, c, v in self.filters:
            x = row.get(c)
            if kind == "eq" and x != v: return False
            if kind == "neq" and x == v: return False
            if kind == "gte" and (x is None or x < v): return False
            if kind == "lte" and (x is None or x > v): return False
            if kind == "in" and x not in v: return False
        return True

    def execute(self):
        err = self.db.fail_on.get((self.name, self.op))
        if err:
            raise RuntimeError(err)
        rows = self.db.tables.setdefault(self.name, [])
        if self.op == "insert":
            row = copy.deepcopy(self.payload)
            if "id" not in row and self.name != "profiles":
                row["id"] = next(self.db._ids)
            if self.name == "shifts":
                row.setdefault("date", "2026-10-26"); row.setdefault("started_at", "t0"); row.setdefault("ended_at", None)
            if self.name == "settlements" and any(r["shift_id"] == row["shift_id"] for r in rows):
                raise RuntimeError('duplicate key value violates unique constraint "settlements_shift_id_key"')
            rows.append(row)
            return Resp([copy.deepcopy(row)])
        if self.op == "upsert":
            row = copy.deepcopy(self.payload)
            for r in rows:
                if r.get("id") == row.get("id"):
                    r.update(row); return Resp([copy.deepcopy(r)])
            rows.append(row); return Resp([copy.deepcopy(row)])
        hit = [r for r in rows if self._match(r)]
        if self.op == "update":
            for r in hit:
                r.update(copy.deepcopy(self.payload))
            return Resp(copy.deepcopy(hit))
        for col, desc in reversed(self.orders):
            hit.sort(key=lambda r: (r.get(col) is None, r.get(col)), reverse=desc)
        if self.n is not None:
            hit = hit[: self.n]
        return Resp(copy.deepcopy(hit))
