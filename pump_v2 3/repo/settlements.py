from core.db import run


def for_shift(shift_id):
    return run("settlements.for_shift", lambda c: c.table("settlements").select("*").eq("shift_id", shift_id).limit(1).execute())


def get(settlement_id):
    return run("settlements.get", lambda c: c.table("settlements").select("*").eq("id", settlement_id).limit(1).execute())


def by_status(statuses):
    def build(c):
        q = c.table("settlements").select("*")
        if len(statuses) == 1:
            q = q.eq("status", statuses[0])
        else:
            q = q.in_("status", list(statuses))
        return q.order("id", desc=True).execute()
    return run("settlements.by_status", build)


def insert(payload):
    return run("settlements.insert", lambda c: c.table("settlements").insert(payload).execute())


def update(settlement_id, payload):
    return run("settlements.update", lambda c: c.table("settlements").update(payload).eq("id", settlement_id).execute())
