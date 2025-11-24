from geoalchemy2 import Geometry
from sqlalchemy import Column, Integer, String, Text
from src.config.database import Base

print(f"Places module loaded. Base id: {id(Base)}")


class BusShelter(Base):
    __tablename__ = "bus_shelters"

    id = Column(Integer, primary_key=True, index=True)
    contract_number = Column(String)
    project_name = Column(String)
    location_name = Column(String)  # Location column in CSV
    code_shelter = Column(String)
    asset_code = Column(String)
    district = Column(String)
    shelter_type = Column(String)  # Type column
    status = Column(String)
    geometry = Column(Geometry("POINT", srid=4326))


class School(Base):
    __tablename__ = "schools"

    id = Column(String, primary_key=True)  # IDSCHOOL
    name = Column(String)  # SCHOOLNAME
    address = Column(Text)
    district = Column(String)
    subdistrict = Column(String)  # TUM
    level = Column(String)
    phone = Column(String)
    geometry = Column(Geometry("POINT", srid=4326))


class PoliceStation(Base):
    __tablename__ = "police_stations"

    id = Column(Integer, primary_key=True)  # id_police
    name = Column(String)
    address = Column(Text)
    phone = Column(String)
    district = Column(String)  # dname
    division = Column(String)
    geometry = Column(Geometry("POINT", srid=4326))


class Museum(Base):
    __tablename__ = "museums"

    id = Column(Integer, primary_key=True)  # id_local
    name = Column(String)
    district = Column(String)  # dname
    address = Column(Text)
    phone = Column(String)
    geometry = Column(Geometry("POINT", srid=4326))


class GasStation(Base):
    __tablename__ = "gas_stations"

    id = Column(Integer, primary_key=True)
    name = Column(String)
    address = Column(Text)
    district = Column(String)  # dname
    brand_type = Column(String)  # type (e.g. NGV)
    geometry = Column(Geometry("POINT", srid=4326))


class TrafficPoint(Base):
    __tablename__ = "traffic_points"

    id = Column(Integer, primary_key=True)
    name = Column(String)  # place
    morning_time = Column(String)
    afternoon_time = Column(String)
    geometry = Column(Geometry("POINT", srid=4326))


class WaterTransport(Base):
    __tablename__ = "water_transport_piers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String)  # place_name
    address = Column(Text)  # place
    geometry = Column(Geometry("POINT", srid=4326))


class TouristAttraction(Base):
    __tablename__ = "tourist_attractions"

    id = Column(Integer, primary_key=True)  # idx
    name = Column(String)  # nname
    description = Column(Text)  # history/activity
    address = Column(Text)
    travel_info = Column(Text)
    open_time = Column(String)
    geometry = Column(Geometry("POINT", srid=4326))


class ContributedPOI(Base):
    __tablename__ = "contributed_pois"

    id = Column(String, primary_key=True)
    name_th = Column(String)
    name_en = Column(String)
    address_th = Column(Text)
    address_en = Column(Text)
    telephone = Column(String)
    website = Column(String)
    lastupdate = Column(String)
    poi_type = Column(String)
    username = Column(String)
    geometry = Column(Geometry("POINT", srid=4326))
