from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, fields
from datetime import datetime
from pathlib import Path

from .models import PlotConfig, PlotStyleConfig, PlotType


STORE_VERSION = 1


class PresetStoreError(RuntimeError):
    pass


class PresetNameConflict(PresetStoreError):
    pass


@dataclass(frozen=True, slots=True)
class PlotPreset:
    name: str
    title: str
    x_label: str
    y_label: str
    plot_type: PlotType
    style: PlotStyleConfig
    updated_at: str

    @classmethod
    def from_config(cls, name: str, config: PlotConfig) -> "PlotPreset":
        cleaned_name = name.strip()
        if not cleaned_name:
            raise ValueError("设置名称不能为空")
        if len(cleaned_name) > 80:
            raise ValueError("设置名称不能超过 80 个字符")
        return cls(
            name=cleaned_name,
            title=config.title,
            x_label=config.x_label,
            y_label=config.y_label,
            plot_type=config.plot_type,
            style=config.style,
            updated_at=datetime.now().astimezone().isoformat(timespec="seconds"),
        )

    def to_config(self) -> PlotConfig:
        return PlotConfig(
            title=self.title,
            x_label=self.x_label,
            y_label=self.y_label,
            plot_type=self.plot_type,
            style=self.style,
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "title": self.title,
            "x_label": self.x_label,
            "y_label": self.y_label,
            "plot_type": self.plot_type,
            "style": asdict(self.style),
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: object) -> "PlotPreset":
        if not isinstance(data, dict):
            raise ValueError("设置记录格式不正确")
        plot_type = data.get("plot_type")
        if plot_type not in {"scatter", "line"}:
            raise ValueError("设置中的图表类型无效")

        style_data = data.get("style")
        if not isinstance(style_data, dict):
            raise ValueError("设置中的图像参数无效")
        valid_style_fields = {item.name for item in fields(PlotStyleConfig)}
        merged_style = asdict(PlotStyleConfig())
        merged_style.update(
            {key: value for key, value in style_data.items() if key in valid_style_fields}
        )

        required_text = ("name", "title", "x_label", "y_label", "updated_at")
        if any(not isinstance(data.get(key), str) for key in required_text):
            raise ValueError("设置中的文字字段无效")

        return cls(
            name=str(data["name"]),
            title=str(data["title"]),
            x_label=str(data["x_label"]),
            y_label=str(data["y_label"]),
            plot_type=plot_type,
            style=PlotStyleConfig(**merged_style),
            updated_at=str(data["updated_at"]),
        )


def default_preset_path() -> Path:
    app_data = os.environ.get("APPDATA")
    if app_data:
        return Path(app_data) / "PlotLab" / "presets.json"
    return Path.home() / ".plotlab" / "presets.json"


class PresetStore:
    """Versioned, atomic JSON persistence for user-created plot presets."""

    def __init__(self, path: Path | str | None = None) -> None:
        self.path = Path(path) if path is not None else default_preset_path()

    def load(self) -> list[PlotPreset]:
        if not self.path.exists():
            return []
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict) or payload.get("version") != STORE_VERSION:
                raise ValueError("不支持的设置文件版本")
            raw_presets = payload.get("presets")
            if not isinstance(raw_presets, list):
                raise ValueError("设置列表格式不正确")
            return [PlotPreset.from_dict(item) for item in raw_presets]
        except (OSError, json.JSONDecodeError, TypeError, ValueError) as error:
            raise PresetStoreError(f"无法读取设置方案：{error}") from error

    def contains(self, name: str) -> bool:
        key = name.strip().casefold()
        return any(item.name.casefold() == key for item in self.load())

    def save_config(self, name: str, config: PlotConfig, overwrite: bool = False) -> PlotPreset:
        preset = PlotPreset.from_config(name, config)
        presets = self.load()
        key = preset.name.casefold()
        existing = next((item for item in presets if item.name.casefold() == key), None)
        if existing is not None and not overwrite:
            raise PresetNameConflict(f"设置方案“{existing.name}”已存在")

        updated = [item for item in presets if item.name.casefold() != key]
        updated.insert(0, preset)
        self._write(updated)
        return preset

    def _write(self, presets: list[PlotPreset]) -> None:
        payload = {
            "version": STORE_VERSION,
            "presets": [preset.to_dict() for preset in presets],
        }
        temp_path = self.path.with_suffix(self.path.suffix + ".tmp")
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temp_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            temp_path.replace(self.path)
        except OSError as error:
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                pass
            raise PresetStoreError(f"无法保存设置方案：{error}") from error
