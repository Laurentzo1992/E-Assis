from ingestion.scraper import PDF_LINK_PATTERN, latest_bulletin, list_bulletins

# Extrait reel de la page taxonomie DGCMEF (verifie le 2026-08-01) : la casse du "n"/"N" dans
# "n°"/"N°" varie d'une publication a l'autre, et une ligne hors-sujet (rapport "SITUATION DES
# MARCHES DE VIVRES...") ne doit pas etre confondue avec un bulletin "Quotidien".
SAMPLE_HTML = """
<td><span class="file file--mime-application-pdf file--application-pdf">
<a href="http://www.dgcmef.gov.bf/sites/default/files/2026-07/Quotidien%20n%C2%B04456.pdf" type="application/pdf">Quotidien n°4456.pdf</a>
</span> (4.18 Mo)</td>
<td><span class="file file--mime-application-pdf file--application-pdf">
<a href="http://www.dgcmef.gov.bf/sites/default/files/2026-07/Quotidien%20N%C2%B04453.pdf" type="application/pdf">Quotidien N°4453.pdf</a>
</span> (3.29 Mo)</td>
<td><span class="file file--mime-application-pdf file--application-pdf">
<a href="http://www.dgcmef.gov.bf/sites/default/files/2026-06/SITUATION_MARCHES_VIVRES.pdf" type="application/pdf">SITUATION DES MARCHES DE VIVRES EXECUTES AU 30 JUIN 2026.pdf</a>
</span> (328.23 Ko)</td>
"""


def _fake_get(monkeypatch, html: str):
    class FakeResponse:
        text = html

        def raise_for_status(self):
            pass

    monkeypatch.setattr("ingestion.scraper.requests.get", lambda *a, **k: FakeResponse())


def test_list_bulletins_ignore_les_publications_hors_quotidien(monkeypatch):
    _fake_get(monkeypatch, SAMPLE_HTML)

    bulletins = list_bulletins()

    assert {b["numero"] for b in bulletins} == {"4456", "4453"}


def test_latest_bulletin_retourne_le_plus_grand_numero(monkeypatch):
    _fake_get(monkeypatch, SAMPLE_HTML)

    bulletin = latest_bulletin()

    assert bulletin["numero"] == "4456"
    assert bulletin["url"].endswith("Quotidien%20n%C2%B04456.pdf")


def test_pattern_capture_les_deux_casses_de_n_degre():
    base = 'href="http://www.dgcmef.gov.bf/sites/default/files/f.pdf" type="application/pdf">Quotidien {}4460.pdf'
    assert PDF_LINK_PATTERN.search(base.format("n°"))
    assert PDF_LINK_PATTERN.search(base.format("N°"))
