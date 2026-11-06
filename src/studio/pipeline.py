"""One bounded backlog task per worker cycle; script approval is always human."""


def run_next(studio):
    claimed = studio.post("/production/claim")
    claimed.raise_for_status()
    task = claimed.json()
    if task["state"] == "idle":
        return None
    task_id, item_id = task["id"], task["item_id"]

    def finish(state, script_id=None):
        response = studio.post(
            f"/production/tasks/{task_id}/finish", json={"state": state, "script_id": script_id}
        )
        response.raise_for_status()
        return response.json()

    try:
        source = studio.post(f"/production/tasks/{task_id}/source")
        if source.status_code != 200:
            return finish("needs_source")
        item = studio.get(f"/items/{item_id}")
        item.raise_for_status()
        if item.json()["status"] in {"DISCOVERED", "MORE_RESEARCH"}:
            research = studio.post(f"/items/{item_id}/research")
            if research.status_code != 200:
                return finish("failed")
        selection = studio.post(f"/production/tasks/{task_id}/select")
        selection.raise_for_status()
        if selection.json()["status"] == "HELD":
            return finish("held")
        script = studio.post(f"/items/{item_id}/scripts")
        if script.status_code != 200 or script.json().get("state") not in {"ready", "approved"}:
            return finish("failed")
        return finish("script_ready", script.json()["id"])
    except Exception:
        # Work and provider reservations remain inspectable/recoverable; never fabricate success.
        return finish("failed")
