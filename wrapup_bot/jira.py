"""최소 Jira REST v2 클라이언트 — 코멘트·전환·멱등 조회만."""
from typing import Optional

TRACK = "wrapup 승인 게시 · %s"


class JiraError(Exception):
    def __init__(self, msg: str, status: Optional[int] = None):
        super().__init__(msg)
        self.status = status


class Jira:
    def __init__(self, base_url: str, email: str, token: str, session=None):
        self.base = base_url.rstrip("/")
        if session is None:
            import requests
            session = requests.Session()
            session.auth = (email, token)
            session.headers.update({"Accept": "application/json"})
        self.s = session

    def _req(self, method: str, path: str, **kw):
        fn = self.s.get if method == "GET" else self.s.post
        try:
            r = fn(self.base + path, timeout=15, **kw)
        except Exception as e:  # 네트워크 오류: 응답 본문·URL 은 싣지 않는다
            raise JiraError("연결 실패 %s" % type(e).__name__)
        if not 200 <= r.status_code < 300:
            raise JiraError("HTTP %d" % r.status_code, r.status_code)
        return r

    def find_tracked_comment(self, key: str, item_id: str) -> Optional[str]:
        r = self._req("GET", "/rest/api/2/issue/%s/comment" % key,
                      params={"orderBy": "-created", "maxResults": 50})
        mark = TRACK % item_id
        for c in r.json().get("comments", []):
            body = c.get("body") or ""
            # id-1 이 id-10 에 걸리지 않도록 표식 뒤가 끝/공백/서식 문자인지 본다
            i = body.find(mark)
            while i != -1:
                tail = body[i + len(mark):i + len(mark) + 1]
                if tail in ("", "_", "\n", " ", "*"):
                    return str(c["id"])
                i = body.find(mark, i + 1)
        return None

    def add_comment(self, key: str, body: str) -> str:
        r = self._req("POST", "/rest/api/2/issue/%s/comment" % key, json={"body": body})
        return str(r.json()["id"])

    def current_status(self, key: str) -> str:
        r = self._req("GET", "/rest/api/2/issue/%s" % key, params={"fields": "status"})
        return r.json()["fields"]["status"]["name"]

    def transition_to(self, key: str, to_status: str) -> None:
        path = "/rest/api/2/issue/%s/transitions" % key
        ts = self._req("GET", path).json().get("transitions", [])
        hit = [t for t in ts if (t.get("to") or {}).get("name", "").strip() == to_status.strip()]
        if not hit:
            raise JiraError("전환 경로 없음")
        if len(hit) > 1:
            raise JiraError("전환 경로 모호")
        self._req("POST", path, json={"transition": {"id": hit[0]["id"]}})
