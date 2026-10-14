from websnapshot.doclinks import related_document

def test_associated_document_subdomain():
    website="https://www.datenschutz.ch/"
    pdf="https://docs.datenschutz.ch/u/d/publikationen/webartikel/webartikel_bekanntgabe_von_daten_ueber_studierende_durch_universitaet_an_ahv.pdf"
    assert related_document(pdf,website)
    assert related_document("https://docs.datenschutz.ch/info.docx",website)
    assert not related_document("https://docs.datenschutz.ch/startseite",website)
    assert not related_document("https://docs.other.ch/report.pdf",website)
    assert not related_document("https://docs.datenschutz.ch.evil.org/report.pdf",website)
