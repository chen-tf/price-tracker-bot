import inspect
from dataclasses import dataclass, field
from typing import List


@dataclass
class ClearSubGoodResponse:
    removed_good_names: List[str] = field(default_factory=lambda: [])

    def to_message(self) -> str:
        if len(self.removed_good_names) == 0:
            return "無可清空的追蹤商品"

        message = "已清空以下物品\n"
        for good_name in self.removed_good_names:
            row = f'''
            ====
            商品名稱:{good_name}
            ====
            '''
            message = message + inspect.cleandoc(row)
        return message
