"""Тесты: команда педагогов в KB, ссылка на чат клиента, синхронизация с сайтом."""
from app.admin_router import _client_contact_block
from app.knowledge.kb import KnowledgeBase
from app.knowledge.site_sync import extract_chunks
from app.memory import Conversation


def test_kb_contains_teachers_with_videos():
    kb = KnowledgeBase()
    docs = kb.search("Кто у вас педагоги?", limit=3)
    assert any(d.category == "team" for d in docs)

    ptitsyn = kb.search("видеовизитка Птицын", limit=1)
    assert ptitsyn and "Птицын Владислав" in ptitsyn[0].title
    assert "Видеовизитка: https://" in ptitsyn[0].text
    assert "Фрагмент урока: https://" in ptitsyn[0].text

    chinese = kb.search("педагог китайского языка", limit=3)
    assert any("Шевченко" in d.title for d in chinese)


def test_kb_team_summary_lists_all_teachers():
    kb = KnowledgeBase()
    summary = next(d for d in kb.documents if d.title.startswith("Команда:"))
    for name in ("Саляхова Алина", "Дмитроченко Юлия", "Птицын Владислав",
                 "Анохин Роман", "Шевченко Дарья"):
        assert name in summary.text


def test_max_contact_link_uses_username():
    conv = Conversation(user_id="5897639", client_name="Иван", max_username="ivan123")
    block = _client_contact_block(conv)
    assert "https://max.ru/ivan123" in block
    assert "Иван" in block


def test_max_contact_without_username_shows_id_only():
    conv = Conversation(user_id="5897639")
    block = _client_contact_block(conv)
    assert "max.ru/chat" not in block
    assert "ID: 5897639" in block


def test_site_sync_extract_chunks():
    html = (
        "<html><head><title>Фоксинбург — школа</title></head><body>"
        "<script>var x = 'мусор, который не должен попасть в базу знаний';</script>"
        "<div>Занятия проходят два раза в неделю по 60 минут в мини-группах до 7 человек.</div>"
        "<p>Стоимость обучения — от 8 200 рублей в месяц при оплате за учебный год.</p>"
        "<li>ок</li></body></html>"
    )
    title, chunks = extract_chunks(html)
    assert title == "Фоксинбург — школа"
    assert len(chunks) == 2
    assert any("8 200" in c for c in chunks)
    assert all("мусор" not in c for c in chunks)


def test_kb_live_documents_searchable():
    kb = KnowledgeBase()
    from app.knowledge.kb import Document, _tokens
    doc = Document(category="site", title="Сайт: тест",
                   text="Запись на новый учебный год 2026/27 открыта")
    doc.tokens = set(_tokens(f"{doc.title} {doc.text}"))
    kb.set_live_documents([doc])
    found = kb.search("запись на учебный год 2026/27", limit=3)
    assert any(d.category == "site" for d in found)


def test_team_reply_lists_teachers_with_links():
    from app.ai_core import team_reply
    kb = KnowledgeBase()
    reply = team_reply(kb, "Кто у вас педагоги английского?")
    assert reply is not None
    assert "Саляхова Алина" in reply and "Птицын Владислав" in reply
    assert "Шевченко" not in reply  # китайский не запрашивали
    assert "Видеовизитка: https://" in reply
    assert "Фрагмент урока: https://" in reply


def test_team_reply_specific_teacher_by_name_form():
    from app.ai_core import team_reply
    kb = KnowledgeBase()
    reply = team_reply(kb, "А есть видео с Алиной?")
    assert reply is not None and "Саляхова Алина" in reply
    assert "Видеовизитка: https://" in reply


def test_team_reply_none_for_unrelated():
    from app.ai_core import team_reply
    kb = KnowledgeBase()
    assert team_reply(kb, "Сколько стоит обучение в месяц?") is None
