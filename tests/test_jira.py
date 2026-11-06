import pytest

from wrapup_bot.jira import Jira, JiraError


class Resp:
    def __init__(self, status, data=None):
        self.status_code = status
        self._data = data

    def json(self):
        return self._data


class FakeSession:
    def __init__(self, routes):
        self.routes = routes  # {(method, path): Resp}
        self.calls = []

    def _do(self, method, url, **kw):
        path = url.split("atlassian.test", 1)[1]
        self.calls.append((method, path, kw))
        return self.routes[(method, path)]

    def get(self, url, **kw):
        return self._do("GET", url, **kw)

    def post(self, url, **kw):
        return self._do("POST", url, **kw)


def jira(routes):
    s = FakeSession(routes)
    return Jira("https://x.atlassian.test", "e", "t", session=s), s


CPATH = "/rest/api/2/issue/PROJ-1/comment"
TPATH = "/rest/api/2/issue/PROJ-1/transitions"


def test_find_tracked_comment_hit():
    j, _ = jira({("GET", CPATH): Resp(200, {"comments": [
        {"id": "10", "body": "다른 것"}, {"id": "11", "body": "본문\n----\n_wrapup 승인 게시 · id-1_"}]})})
    assert j.find_tracked_comment("PROJ-1", "id-1") == "11"


def test_find_tracked_comment_miss():
    j, _ = jira({("GET", CPATH): Resp(200, {"comments": [{"id": "10", "body": "wrapup 승인 게시 · id-10"}]})})
    assert j.find_tracked_comment("PROJ-1", "id-1") is None


def test_add_comment_posts_v2_body():
    j, s = jira({("POST", CPATH): Resp(201, {"id": "99"})})
    assert j.add_comment("PROJ-1", "본문") == "99"
    assert s.calls[0][2]["json"] == {"body": "본문"}


def test_current_status():
    j, _ = jira({("GET", "/rest/api/2/issue/PROJ-1"): Resp(200, {"fields": {"status": {"name": "작업요청"}}})})
    assert j.current_status("PROJ-1") == "작업요청"


def trans(*names):
    return Resp(200, {"transitions": [{"id": str(i), "to": {"name": n}} for i, n in enumerate(names, 1)]})


def test_transition_exact_one():
    j, s = jira({("GET", TPATH): trans("반려", "진행 중"), ("POST", TPATH): Resp(204)})
    j.transition_to("PROJ-1", "진행 중")
    assert s.calls[-1][2]["json"] == {"transition": {"id": "2"}}


def test_transition_name_whitespace():
    j, s = jira({("GET", TPATH): trans(" 진행 중 "), ("POST", TPATH): Resp(204)})
    j.transition_to("PROJ-1", "진행 중")
    assert s.calls[-1][0] == "POST"


def test_transition_none_raises():
    j, _ = jira({("GET", TPATH): trans("반려")})
    with pytest.raises(JiraError, match="전환 경로 없음"):
        j.transition_to("PROJ-1", "진행 중")


def test_transition_ambiguous_raises():
    j, _ = jira({("GET", TPATH): trans("진행 중", "진행 중")})
    with pytest.raises(JiraError, match="전환 경로 모호"):
        j.transition_to("PROJ-1", "진행 중")


def test_http_error_raises_with_status():
    j, _ = jira({("POST", CPATH): Resp(403, {"errorMessages": ["secret detail"]})})
    with pytest.raises(JiraError) as e:
        j.add_comment("PROJ-1", "x")
    assert e.value.status == 403 and "secret detail" not in str(e.value)
