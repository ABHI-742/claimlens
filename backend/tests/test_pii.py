from app.services.pii import PiiMasker


def test_masks_ssn_email_and_valid_card():
    text = "SSN 123-45-6789, email jane@example.com, card 4111 1111 1111 1111."
    result = PiiMasker().mask(text)

    assert "123-45-6789" not in result.text
    assert "jane@example.com" not in result.text
    assert "4111 1111 1111 1111" not in result.text
    assert result.token_map["[SSN_1]"] == "123-45-6789"
    assert result.token_map["[EMAIL_1]"] == "jane@example.com"
    assert result.token_map["[CARD_1]"] == "4111 1111 1111 1111"


def test_same_value_gets_same_token():
    result = PiiMasker().mask("Call 555-123-4567. Again: 555-123-4567.")
    assert result.text.count("[PHONE_1]") == 2
    assert "[PHONE_2]" not in result.text


def test_number_failing_luhn_is_not_masked_as_card():
    result = PiiMasker().mask("Invoice 1234567890123 total 500")
    assert not any(token.startswith("[CARD") for token in result.token_map)
