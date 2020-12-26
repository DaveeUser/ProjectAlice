from pathlib import Path
from typing import Union

from flask import jsonify, request, send_from_directory
from flask_classful import route

from core.device.model.Device import Device
from core.device.model.DeviceType import DeviceType
from core.interface.model.Api import Api
from core.util.Decorators import ApiAuthenticated


class MyHomeApi(Api):
	route_base = f'/api/{Api.version()}/myHome/'


	def __init__(self):
		super().__init__()


	@route('/', methods=['GET'])
	@ApiAuthenticated
	def getData(self):
		try:
			return jsonify(data={
				'locations': {location.id: location.toDict() for location in self.LocationManager.locations.values()},
				'constructions': {construction.id: construction.toDict() for construction in self.LocationManager.constructions.values()},
				'furnitures': {furniture.id: furniture.toDict() for furniture in self.LocationManager.furnitures.values()},
				'devices': {device.uid: device.toDict() for device in self.DeviceManager.devices.values()}
			})
		except:
			return jsonify(success=False)


	@route('/locations/<location>/', methods=['GET'])
	@ApiAuthenticated
	def getLocation(self, location: Union[int, str]):
		try:
			try:
				locId = int(location)
				location = self.LocationManager.getLocation(locId=locId)
				if location:
					return jsonify(location=location.toDict())
				else:
					return jsonify(success=False)
			except ValueError:
				location = self.LocationManager.getLocation(locationName=location, locationSynonym=location)
				if location:
					return jsonify(location=location.toDict())
				else:
					return jsonify(success=False)

		except Exception as e:
			self.logError(f'Something went wrong retrieving location {location} {e}')
			return jsonify(success=False)


	@route('/locations/', methods=['PUT'])
	@ApiAuthenticated
	def addLocation(self):
		try:
			location = self.LocationManager.addNewLocation(data=request.json)
			if location:
				return jsonify(location=location.toDict())
			else:
				return jsonify(success=False)
		except Exception as e:
			self.logError(f'Something went wrong creating a new location {e}')
			return jsonify(success=False)


	@route('/furniture/', methods=['PUT'])
	@ApiAuthenticated
	def addFurniture(self):
		try:
			furniture = self.LocationManager.addNewFurniture(data=request.json)
			if furniture:
				return jsonify(furniture=furniture.toDict())
			else:
				return jsonify(success=False)
		except Exception as e:
			self.logError(f'Something went wrong creating a new furniture {e}')
			return jsonify(success=False)


	@route('/constructions/', methods=['PUT'])
	@ApiAuthenticated
	def addConstruction(self):
		try:
			construction = self.LocationManager.addNewConstruction(data=request.json)
			if construction:
				return jsonify(construction=construction.toDict())
			else:
				return jsonify(success=False)
		except Exception as e:
			self.logError(f'Something went wrong creating a new construction {e}')
			return jsonify(success=False)


	@route('/locations/<locationId>/', methods=['PATCH'])
	@ApiAuthenticated
	def updateLocation(self, locationId: str):
		try:
			return jsonify(success=self.LocationManager.updateLocation(int(locationId), request.json).toDict())
		except Exception as e:
			self.logError(f'Failed saving location {e}')
			return jsonify(success=False)


	@route('/furniture/<furnitureId>/', methods=['PATCH'])
	@ApiAuthenticated
	def updateFurniture(self, furnitureId: str):
		try:
			return jsonify(success=self.LocationManager.updateFurniture(int(furnitureId), request.json).toDict())
		except Exception as e:
			self.logError(f'Failed saving furniture {e}')
			return jsonify(success=False)


	@route('/constructions/<constructionId>/', methods=['PATCH'])
	@ApiAuthenticated
	def updateConstruction(self, constructionId: str):
		try:
			return jsonify(success=self.LocationManager.updateConstruction(int(constructionId), request.json).toDict())
		except Exception as e:
			self.logError(f'Failed saving construction {e}')
			return jsonify(success=False)


	@route('/devices/<deviceUid>/', methods=['PATCH'])
	@ApiAuthenticated
	def updateDevice(self, deviceUid: str):
		try:
			return jsonify(success=self.DeviceManager.updateDeviceDisplay(deviceUid, request.json).toDict())
		except Exception as e:
			self.logError(f'Failed saving device {e}')
			return jsonify(success=False)


	@route('/locations/<locationId>/', methods=['DELETE'])
	@ApiAuthenticated
	def deleteLocation(self, locationId: str):
		try:
			self.LocationManager.deleteLocation(int(locationId))
			return jsonify(success=True)
		except Exception as e:
			self.logError(f'Failed deleting location {e}')
			return jsonify(success=False)


	@route('/furniture/<furnitureId>/', methods=['DELETE'])
	@ApiAuthenticated
	def deleteFurniture(self, furnitureId: str):
		try:
			self.LocationManager.deleteFurniture(int(furnitureId))
			return jsonify(success=True)
		except Exception as e:
			self.logError(f'Failed deleting furniture {e}')
			return jsonify(success=False)


	@route('/constructions/<constructionId>/', methods=['DELETE'])
	@ApiAuthenticated
	def deleteConstruction(self, constructionId: str):
		try:
			self.LocationManager.deleteConstruction(int(constructionId))
			return jsonify(success=True)
		except Exception as e:
			self.logError(f'Failed deleting construction {e}')
			return jsonify(success=False)


	@route('/devices/<deviceUid>/', methods=['DELETE'])
	@ApiAuthenticated
	def deleteDevice(self, deviceUid: str):
		try:
			self.DeviceManager.deleteDevice(deviceUid)
			return jsonify(success=True)
		except Exception as e:
			self.logError(f'Failed deleting device {e}')
			return jsonify(success=False)


	@route('/locations/floors/', methods=['GET'])
	def getFloorsList(self):
		try:
			return jsonify(data=[image.stem for image in Path(self.Commons.rootDir(), 'core/webApi/static/images/floors/').glob('*.png')])
		except:
			return jsonify(success=False)


	@route('/furniture/tiles/', methods=['GET'])
	def getFurnitureList(self):
		try:
			return jsonify(data=[image.stem for image in Path(self.Commons.rootDir(), 'core/webApi/static/images/furniture/').glob('*.png')])
		except:
			return jsonify(success=False)


	@route('/constructions/tiles/', methods=['GET'])
	def getConstructionList(self):
		try:
			return jsonify(data=[image.stem for image in Path(self.Commons.rootDir(), 'core/webApi/static/images/constructions/').glob('*.png')])
		except:
			return jsonify(success=False)


	@route('/locations/floors/<imageId>.png', methods=['GET'])
	def getFloor(self, imageId: str):
		try:
			return send_from_directory('static/images/floors', f'{imageId}.png')
		except:
			return jsonify(success=False)


	@route('/furniture/<imageId>.png', methods=['GET'])
	def getFurniture(self, imageId: str):
		try:
			return send_from_directory('static/images/furniture', f'{imageId}.png')
		except:
			return jsonify(success=False)


	@route('/constructions/<imageId>.png', methods=['GET'])
	def getConstruction(self, imageId: str):
		try:
			return send_from_directory('static/images/constructions', f'{imageId}.png')
		except:
			return jsonify(success=False)


	@route('/devices/<uid>/device.png', methods=['GET'])
	def getDeviceIcon(self, uid: str):
		try:
			device: Device = self.DeviceManager.getDevice(uid=uid)
			file = device.getDeviceIcon()
			return send_from_directory(file.parent, f'{file.stem}.png')
		except:
			return jsonify(success=False)


	@route('/devices/<uid>/onClick/', methods=['PATCH'])
	@ApiAuthenticated
	def deviceClick(self, uid: str):
		try:
			device = self.DeviceManager.getDevice(uid=uid)
			device.onUIClick()
			return jsonify(success=True)
		except:
			return jsonify(success=False)


	@route('/deviceTypes/', methods=['GET'])
	@ApiAuthenticated
	def getDeviceTypes(self):
		try:
			data = dict()
			for skillName, deviceType in self.DeviceManager.deviceTypes.items():
				data.setdefault(skillName, list())
				data[skillName] = [dType.toDict() for dType in deviceType.values()]

			return jsonify(types=data)
		except Exception as e:
			self.logError(f'Cannot return device type list {e}')
			return jsonify(success=False)


	@route('/deviceTypes/<skillName>/<deviceType>.png', methods=['GET'])
	def getDeviceTypeIcon(self, skillName: str, deviceType: str):
		try:
			dType: DeviceType = self.DeviceManager.getDeviceType(skillName=skillName, deviceType=deviceType)
			file = dType.getDeviceTypeIcon()
			return send_from_directory(file.parent, f'{file.stem}.png')
		except Exception as e:
			self.logError(f'Failed retrieving device type icon {e}')
			return jsonify(success=False)
