class ExcelFormatException(Exception):
    def __init__(self, msg):
        self.msg = msg

    def __str__(self):
        return self.msg or '엑셀 파일을 읽을 수 없습니다.'


class ExtractImageException(Exception):
    def __init__(self, msg):
        self.msg = msg

    def __str__(self):
        return self.msg or '이미지 추출에 실패했습니다.'