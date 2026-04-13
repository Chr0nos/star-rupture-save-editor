import struct
import zlib
import json
from pathlib import Path
from pydantic import (
    BaseModel,
    NonNegativeFloat,
    NonNegativeInt,
    Field,
    validate_call,
    model_validator,
)
from typing import Any, Self
import click
import logging
import structlog
from datetime import timedelta

# Special thanks to https://github.com/AlienXAXS/StarRupture-Save-Manager
# For sharing the way that crimson jar is messing the .sav files to prevent us to modify it...

STAR_RUPTURE_STEAM_GAME_ID = 1631270

logger = structlog.get_logger(__name__)
logging.basicConfig(
    level=logging.DEBUG,
    format="%(message)s",
)
structlog.configure(
    wrapper_class=structlog.make_filtering_bound_logger(logging.DEBUG),
    logger_factory=structlog.PrintLoggerFactory(),
)


class StarRuptureSaveMetadata(BaseModel):
    timestamp: int
    world_time_seconds: NonNegativeFloat = Field(alias="worldTimeSeconds")
    is_in_tutorial: bool
    version: NonNegativeInt

    def save(self, destination: str) -> None:
        metadata = {
            "timestamp": str(self.timestamp),
            "worldTimeSeconds": str(self.world_time_seconds),
            "bIsInTutorial": self.is_in_tutorial,
            "version": self.version,
        }
        with open(destination, "w") as fp:
            json.dump(metadata, fp, indent=4)
        logger.info("Saved metadata", path=destination)

    @classmethod
    def from_sav(cls, obj: dict[str, Any]) -> "StarRuptureSaveMetadata":
        return cls.model_validate(
            dict(
                timestamp=int(obj["timestamp"]),
                version=2,
                is_in_tutorial=False,
                worldTimeSeconds=obj["worldTimeSeconds"],
            ),
            by_alias=True,
        )


class StarRuptureCorporation(BaseModel):
    name: str
    hidden: bool = Field(default=False, alias="bHidden")
    reputation: NonNegativeInt
    level: NonNegativeInt
    level_rewards_claimed: list[NonNegativeInt] = Field(
        alias="levelRewardsClaimed", default_factory=list
    )
    upgraded_buildings_claimed: list[Any] = Field(
        alias="upgradedBuildingsClaimed", default_factory=list
    )
    research_points_tier_one: NonNegativeInt = Field(alias="researchPointsTier1")
    research_points_tier_two: NonNegativeInt = Field(alias="researchPointsTier2")


class StarRuptureGame:
    def __init__(self, world: dict[str, Any], key_path_delimiter: str = "."):
        self._obj = world
        self._key_path_delimiter = key_path_delimiter

    @classmethod
    def load(cls, path: str) -> "StarRuptureGame":
        extenssion = path.split(".")[-1]
        match extenssion:
            case "json":
                return cls.load_json(path)
            case "sav":
                return cls.load_save(path)
            case _:
                raise ValueError(f"Unknow file extenssion {extenssion}")

    @classmethod
    def load_json(cls, path: str) -> "StarRuptureGame":
        logger.info("Loading .json", path=path)
        if not path.endswith(".json"):
            raise ValueError
        return cls(world=json.loads(Path(path).read_text(encoding="utf-8")))

    @classmethod
    def load_save(cls, path: str) -> "StarRuptureGame":
        logger.info("Loading .sav", path=path)
        if not path.endswith(".sav"):
            raise ValueError

        data = Path(path).read_bytes()
        raw = zlib.decompress(data[4:])
        obj = json.loads(raw.decode("utf-8"))
        logger.info("File loaded", path=path)
        return cls(world=obj)

    @validate_call
    def save(self, output_slot: str) -> None:
        raw = json.dumps(self._obj, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        comp = zlib.compress(raw, 9)

        header = struct.pack("<I", len(raw))
        sav_path = f"{output_slot}.sav"
        Path(sav_path).write_bytes(header + comp)
        metadata = StarRuptureSaveMetadata.from_sav(self._obj)
        metadata.save(f"{output_slot}.met")
        logger.info("Save created", destination=sav_path)

    @validate_call
    def save_to_json(self, destination: str) -> None:
        Path(destination).write_text(
            json.dumps(self._obj, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        logger.info("Saved game", destination=destination)

    def _split_path(self, key: str) -> list[str]:
        return key.split(self._key_path_delimiter)

    @validate_call
    def __getitem__(self, key: str) -> Any:
        value = self._obj
        for part in key.split("."):
            try:
                value = value[part]
            except KeyError:
                logger.error("No such key", key=key, part=part)
                raise
        return value

    @validate_call
    def remove(self, key: str) -> bool:
        logger.debug("Removing", key=key)
        parts = self._split_path(key)
        container = self._obj
        for part in parts[0:-1]:
            try:
                container = container[part]
            except KeyError:
                logger.warning("Key was missing", key=key)
                return False
        try:
            container.pop(parts[-1])
            return True
        except KeyError:
            return False

    @validate_call
    def replace(self, key: str, new_value: Any) -> None:
        logger.debug("Replacing", key=key, new_value=new_value)
        parts = self._split_path(key)
        container = self._obj

        for part in parts[:-1]:
            if part not in container or not isinstance(container[part], dict):
                container[part] = {}
            container = container[part]

        container[parts[-1]] = new_value

    @validate_call
    def get_player_ids(self) -> list[int]:
        players = self._obj["itemData"]["GameStateData"]["allCharactersBaseSaveData"][
            "allPlayersSaveData"
        ]
        return list(players.keys())

    def get_player(self, player_id: int) -> "StarRupturePlayer":
        if player_id not in self["itemData.GameStateData.allCharactersBaseSaveData"]:
            raise ValueError
        player = StarRupturePlayer(player_id, self)
        return player

    @property
    def playtime(self) -> timedelta:
        return timedelta(seconds=self["itemData.GameStateData.playtimeDuration"])

    @validate_call
    def get_datapoints(self) -> int:
        return self["itemData.CrCorporationsOwner.dataPoints"]

    @validate_call
    def set_datapoints(self, value: NonNegativeInt):
        self.replace("itemData.CrCorporationsOwner.dataPoints", value)

    def get_corporations(self) -> list[StarRuptureCorporation]:
        corporations = []
        for raw_corporation in self["itemData.CrCorporationsOwner.corporations"]:
            corporation = StarRuptureCorporation.model_validate(raw_corporation, by_alias=True)
            corporations.append(corporation)
        return corporations


class StarRupturePlayerAttribute(BaseModel):
    current: NonNegativeInt
    min: NonNegativeInt
    max: NonNegativeInt

    @model_validator(mode="after")
    def validate_model(self) -> Self:
        if self.min < self.max:
            raise ValueError
        return self

    @staticmethod
    def is_settable(name: str) -> bool:
        return name in StarRupturePlayerAttribute.__SETTABLE_ATTRIBUTES

    __SETTABLE_ATTRIBUTES = (
        "health",
        "energy",
        "shield",
        "hydration",
        "calories",
        "toxicity",
        "radiation",
        "heat",
        "drain",
        "corrosion",
        "oxygen",
        "medToolCharge",
        "grenadeCharge",
        "movementSpeedMultiplier",
    )


class StarRupturePlayer:
    def __init__(self, player_id: int, world: StarRuptureGame) -> None:
        self.player_id = player_id
        self._world = world

    @property
    def key(self) -> str:
        return (
            f"itemData.GameStateData.allCharactersBaseSaveData.allPlayersSaveData.{self.player_id}"
        )

    def get_position(self) -> tuple[float, float, float]:
        return tuple(
            self._world[f"{self.key}.survivalData.transform.translation.{axis}"]
            for axis in ("x", "y", "z")
        )

    @validate_call
    def set_position(self, x: float, y: float, z: float) -> None:
        key_prefix = f"{self.key}.survivalData.transform.translation."
        self._world.replace(f"{key_prefix}.x", x)
        self._world.replace(f"{key_prefix}.y", y)
        self._world.replace(f"{key_prefix}.z", z)

    @validate_call
    def set_survival_attribute(self, name: str, new_value: StarRupturePlayerAttribute) -> None:
        if not StarRupturePlayerAttribute.is_settable(name):
            raise ValueError
        key_prefix = f"{self.key}.survivalData"
        self._world.replace(f"{key_prefix}.{name}", new_value.model_dump())


def migrate_from_testing(save_path: str, output_slot: str) -> None:
    world = StarRuptureGame.load(save_path)
    world.remove("gameVersion")
    world.replace("version", 2)
    for player_id in world.get_player_ids():
        key = f"itemData.GameStateData.allCharactersBaseSaveData.allPlayersSaveData.{player_id}.lastPlayedGameVersion"
        world.remove(key)
    world.save(output_slot)


@click.group()
def cli() -> None:
    """StarRupture save tool"""
    pass


@cli.command()
@click.argument("input_file")
@click.argument("output_file")
def decode(input_file, output_file) -> None:
    """Decode .sav -> JSON"""
    StarRuptureGame.load(input_file).save_to_json(output_file)


@cli.command()
@click.argument("input_file")
@click.argument("output_slot")
def encode(input_file, output_slot) -> None:
    """Encode JSON -> .sav"""
    StarRuptureGame.load_json(input_file).save(output_slot)


@cli.command()
@click.argument("input_file")
def list_players(input_file: str) -> None:
    """List all players and their positions"""
    world = StarRuptureGame.load(input_file)
    for player_id in world.get_player_ids():
        player = StarRupturePlayer(player_id, world)
        logger.info("Player found", player_id=player_id, position=player.get_position())


@cli.command()
@click.argument("input_file")
@click.argument("output_slot")
@click.argument("player_id", type=int)
@click.argument("property", type=str)
@click.argument("min", type=int)
@click.argument("max", type=int)
@click.argument("current", type=int)
def set_player_attribute(
    input_file: str,
    output_slot: str,
    player_id: int,
    property: str,
    min: int,
    max: int,
    current: int,
) -> None:
    """Set a survival attribute for a player"""
    world = StarRuptureGame.load(input_file)
    player = world.get_player(player_id)
    player.set_survival_attribute(
        property, StarRupturePlayerAttribute(current=current, min=min, max=max)
    )
    world.save(output_slot)


@cli.command()
@click.argument("save_slot")
@click.argument("output_slot")
def migrate(save_slot: str, output_slot: str) -> None:
    """Run migration from testing branch to be able to play back on the main branch"""
    migrate_from_testing(save_slot, output_slot)


@cli.command()
@click.argument("input_file")
def list_corporations(input_file: str) -> None:
    """List all corporations and their stats"""
    world = StarRuptureGame.load(input_file)
    for corporation in world.get_corporations():
        logger.info(
            "Corporation found",
            name=corporation.name,
            _level=corporation.level,
            reputation=corporation.reputation,
            hidden=corporation.hidden,
        )


@cli.command()
@click.argument("input_file")
@click.argument("output_slot")
@click.argument("datapoints")
def set_datapoints(input_file: str, output_slot: str, datapoints: int) -> None:
    """Set the datapoints balance"""
    world = StarRuptureGame.load(input_file)
    world.set_datapoints(datapoints)
    world.save(output_slot)


if __name__ == "__main__":
    cli()
