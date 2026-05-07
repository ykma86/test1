"""테스트 공통 픽스처: 외부 HTTP 호출 자동 mock."""
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture(autouse=True)
def _mock_external_http():
    """main 네임스페이스의 HTTP 외부 호출 함수를 None으로 자동 mock.

    실제 네트워크를 차단해 테스트 속도를 높이고 불안정성을 제거한다.
    개별 테스트에서 patch()로 덮어쓸 수 있다.
    """
    with patch("main.fetch_put_call_ratio", return_value=None), \
         patch("main.fetch_fear_greed", return_value=None):
        yield
