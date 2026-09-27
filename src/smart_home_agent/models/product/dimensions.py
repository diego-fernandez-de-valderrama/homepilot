from catalog_ingestion.domain.enums import Dimension

CAPABILITY_DIMENSIONS = (Dimension.ECOSYSTEM, Dimension.VOICE_ASSISTANT, Dimension.PROTOCOL)
# An upgrade may also win on the phone platforms its app supports (canonical iOS / Android facts).
UPGRADE_DIMENSIONS = (*CAPABILITY_DIMENSIONS, Dimension.MOBILE_OS)
