import logging

from google.genai import types

from catalog_ingestion.llm.client import without_automatic_function_calling


def test_automatic_function_calling_is_disabled_by_default():
    config = types.GenerateContentConfig(temperature=0.0, tools=[types.Tool(url_context=types.UrlContext())])
    result = without_automatic_function_calling(config)
    assert result.automatic_function_calling is not None
    assert result.automatic_function_calling.disable is True
    assert result.tools == config.tools and result.temperature == 0.0
    assert config.automatic_function_calling is None  # the caller's config is not mutated


def test_explicit_afc_configuration_is_kept():
    explicit = types.AutomaticFunctionCallingConfig(disable=False, maximum_remote_calls=3)
    config = types.GenerateContentConfig(automatic_function_calling=explicit)
    assert without_automatic_function_calling(config).automatic_function_calling == explicit


def test_sdk_does_not_warn_about_afc(caplog):
    """Runs the SDK code path that emits the warning, without a network call."""
    from google.genai import _extra_utils

    config = without_automatic_function_calling(types.GenerateContentConfig())
    with caplog.at_level(logging.WARNING, logger="google_genai"):
        assert _extra_utils.should_disable_afc(config) is True
    assert not caplog.records
