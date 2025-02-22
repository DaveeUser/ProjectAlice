#  Copyright (c) 2021
#
#  This file, UserManager.py, is part of Project Alice.
#
#  Project Alice is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <https://www.gnu.org/licenses/>
#
#  Last modified: 2021.04.13 at 12:56:47 CEST

import bcrypt
import jwt
from pathlib import Path
from time import time
from typing import Any, Dict, Optional, Union

from core.base.model.Manager import Manager
from core.commons import constants
from core.user.model.AccessLevels import AccessLevel
from core.user.model.User import User


class UserManager(Manager):
	DATABASE = {
		'users': [
			'id INTEGER PRIMARY KEY',
			'username TEXT NOT NULL',
			'state TEXT NOT NULL',
			'accessLevel TEXT NOT NULL',
			'pin BLOB',
			'lang TEXT',
			'tts TEXT',
			'ttsLanguage TEXT',
			'ttsType TEXT',
			'ttsVoice TEXT',
			'apiToken TEXT'
		]
	}


	def __init__(self):
		super().__init__(databaseSchema=self.DATABASE)
		self._users: Dict[str: User] = dict()
		self._validtokens: Dict[str: User] = dict()


	def onStart(self):
		super().onStart()
		self._loadUsers()
		self.logInfo(f'Loaded **{len(self._users)}** user', plural='user')


	def _loadUsers(self):
		rows = self.databaseFetch(tableName='users', query='SELECT * FROM :__table__')
		for row in rows:
			user = User(row)
			self._users[user.name] = user
			self._validtokens[user.apiToken] = user


	def createApiToken(self, user: User, save: bool = True) -> str:
		token = jwt.encode({'user': user.name, 'birth': time()}, 'projectalice', algorithm='HS256')
		self._validtokens[token] = user

		if save:
			user.apiToken = token
			self.DatabaseManager.update(
				tableName='users',
				callerName=self.name,
				values={'apiToken': token},
				row=('username', user.name))

		return token


	@property
	def users(self) -> dict:
		return self._users


	@staticmethod
	def getHashedPassword(password: int, rounds: int = 12) -> bytes:
		return bcrypt.hashpw(str(password).encode(), bcrypt.gensalt(rounds=rounds))


	def checkPinCode(self, user: User, password: str):
		return user in self._users.values() and user.checkPassword(password)


	# noinspection SqlResolve
	def addNewUser(self, name: str, access: str = 'guest', state: str = 'home', pinCode: int = None):
		hashedPassword = self.getHashedPassword(pinCode or 1234)

		insertId = self.databaseInsert(
			tableName='users',
			values={
				'username'   : name.lower(),
				'accessLevel': access,
				'state'      : state,
				'pin'        : hashedPassword,
				'lang'       : self.LanguageManager.activeLanguageAndCountryCode
			})
		if insertId > -1:
			self._users[name] = User({
				'id'         : insertId,
				'username'   : name.title(),
				'accessLevel': access,
				'state'      : state,
				'pin'        : hashedPassword,
				'lang'       : self.LanguageManager.activeLanguageAndCountryCode,
				'tts'        : '',
				'ttsLanguage': '',
				'ttsType'    : '',
				'ttsVoice'   : '',
				'apiToken'   : ''
			})


	def addUserPinCode(self, name: str, pinCode: int):
		self.DatabaseManager.update(
			tableName='users',
			callerName=self.name,
			values={'pin': self.getHashedPassword(pinCode)},
			row=('username', name))


	# noinspection SqlResolve
	def deleteUser(self, username: str, keepWakeword: bool = False):
		self.DatabaseManager.delete(
			tableName='users',
			callerName=self.name,
			query='DELETE FROM :__table__ WHERE username = :username',
			values={
				'username': username
			}
		)

		self._users.pop(username)

		if not keepWakeword:
			path = Path(self.Commons.rootDir(), 'trained/hotwords', username)
			if path.exists():
				path.unlink()


	def getUserAccessLevel(self, username: str) -> Optional[Any]:
		if username not in self._users:
			return None

		return self._users[username].accessLevel


	def getUser(self, username: str) -> Optional[User]:
		return self._users.get(username.lower(), None)


	def getUserById(self, userId: int) -> Optional[User]:
		return next((user for user in self._users.values() if user.id == userId), None)


	def getAllUserNames(self, skipGuests: bool = True) -> list:
		"""
			Return all users
			:return: list
		"""
		return [k for k in self._users if not skipGuests or self._users[k] != 'guest']


	def checkIfAllUser(self, state: str) -> bool:
		"""
		Checks if the given state applies to all users (except for guests)
		:param state: the state to check
		:return: boolean
		"""
		return self._users and all(self._users[username].state == state for username in self.getAllUserNames())


	def checkIfUser(self, user: str, state: str) -> bool:
		"""
		Checks if the given state applies to the user
		:param user: str
		:param state: the state to check
		:return: boolean
		"""
		return self._users[user].state == state


	def goingBed(self, user: str = 'all'):
		if user == 'all':
			for user in self._users:
				self.updateUserState(name=user, state='goingBed')
		# self._users[user].state('goingBed')
		else:
			self._users[user].home = True
			self._users[user].goingBed = True
			self._users[user].sleeping = False


	def sleeping(self, user: str = 'all'):
		if user == 'all':
			for user in self._users:
				self.updateUserState(name=user, state='sleeping')
		# self._users[user].state('sleeping')
		else:
			self._users[user].home = True
			self._users[user].goingBed = False
			self._users[user].sleeping = True


	def wakeup(self, user: str = 'all'):
		if user == 'all':
			for user in self._users:
				self.updateUserState(name=user, state='home')
		# self._users[user].state('home')
		else:
			self._users[user].home = True
			self._users[user].goingBed = False
			self._users[user].sleeping = False


	def leftHome(self, user: str = 'all'):
		if user == 'all':
			for user in self._users:
				self.updateUserState(name=user, state='out')
		# self._users[user].state('out')
		else:
			self._users[user].home = False
			self._users[user].goingBed = False
			self._users[user].sleeping = False


	def home(self, user: str = 'all'):
		if user == 'all':
			for user in self._users:
				self.updateUserState(name=user, state='home')
		# self._users[user].state('home')
		else:
			self._users[user].home = True
			self._users[user].goingBed = False
			self._users[user].sleeping = False


	# todo - Store user state in memory and write it to database onStop
	def updateUserState(self, name, state):
		self.DatabaseManager.update(
			tableName='users',
			callerName=self.name,
			values={'state': state},
			row=('username', name))
		self._loadUsers()


	def hasAccessLevel(self, user: str, requiredAccessLevel: Union[AccessLevel, int]) -> bool:
		if isinstance(requiredAccessLevel, AccessLevel):
			requiredAccessLevel = requiredAccessLevel.value

		return user.lower() in self._users and AccessLevel[
			self._users[user.lower()].accessLevel.upper()].value <= requiredAccessLevel


	def apiTokenValid(self, token: str) -> bool:
		return token != '' and token in self._validtokens


	def apiTokenLevel(self, token: str) -> AccessLevel:
		return self._validtokens[token].accessLevel if token in self._validtokens else constants.UNKNOWN


	def getUserByAPIToken(self, token: str) -> Optional[User]:
		return self._validtokens.get(token, None)
