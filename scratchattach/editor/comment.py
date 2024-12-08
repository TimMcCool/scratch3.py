from __future__ import annotations

from . import base, block, sprite


class Comment(base.IDComponent):
    def __init__(self, _id: str = None, _block: block.Block = None, x: int = 0, y: int = 0, width: int = 100,
                 height: int = 100, minimized: bool = False,
                 text: str = '', *, _block_id: str = None, _sprite: sprite.Sprite = None):
        self.block = _block
        self._block_id = _block_id
        """
        ID of connected block. Will be set to None upon sprite initialization when the block attribute is updated to the relevant Block.
        """

        self.x = x
        self.y = y

        self.width = width
        self.height = height

        self.minimized = minimized
        self.text = text

        super().__init__(_id, _sprite)

    def __repr__(self):
        return f"Comment<{self.text[:10]!r}...>"

    @property
    def block_id(self):
        if self.block is not None:
            return self.block.id
        elif self._block_id is not None:
            return self._block_id
        else:
            return None

    @staticmethod
    def from_json(data: tuple[str, dict]):
        assert len(data) == 2
        _id, data = data

        _block_id = data.get("blockId")

        x = data.get("x", 0)
        y = data.get("y", 0)

        width = data.get("width", 100)
        height = data.get("height", 100)

        minimized = data.get("minimized", False)
        text = data.get("text")

        ret = Comment(_id, None, x, y, width, height, minimized, text, _block_id=_block_id)
        return ret

    def to_json(self) -> dict:
        return {
            "blockId": self.block_id,
            "x": self.x, "y": self.y,
            "width": self.width, "height": self.height,
            "minimized": self.minimized,
            "text": self.text,
        }

    def link_using_sprite(self):
        if self._block_id is not None:
            self.block = self.sprite.find_block(self._block_id, "id")
            if self.block is not None:
                self._block_id = None