from pathlib import PurePosixPath

import pytest


@pytest.mark.asyncio
async def test_client_list_broken_file_name(pair_factory):
    input_bytes = b"type=file;size=1;modify=19700101000000; doc_\xd3\xc2\xd2.txt\r\n"
    expected = (PurePosixPath('doc_���.txt'), {'modify': '19700101000000', 'size': '1', 'type': 'file'})
    async with pair_factory() as pair:
        result = pair.client.parse_mlsx_line(input_bytes)
        assert result == expected
