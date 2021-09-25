#  Copyright (c) 2021
#
#  This file, GithubCloner.py, is part of Project Alice.
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
#  Last modified: 2021.08.21 at 12:56:45 CEST

import json
import requests
import shutil
import time
from pathlib import Path
from dulwich.porcelain import commit, push, status, open_repo, clone, remote_add, pull, RemoteExists
from dulwich import porcelain
from dulwich.repo import Repo
from dulwich.errors import NotGitRepository

from core.base.SuperManager import SuperManager
from core.base.model.ProjectAliceObject import ProjectAliceObject


class GithubCloner(ProjectAliceObject):
	NAME = 'GithubCloner'


	def __init__(self, baseUrl: str, dest: Path, skillName: str = None):
		super().__init__()
		self._baseUrl = baseUrl
		self._dest = dest
		self._skillName = skillName
		self._repo = None
		self._modified = True


	@classmethod
	def getGithubAuth(cls) -> tuple:
		"""
		Returns the users configured username and token for github as a tuple
		When one of the values is not supplied None is returned.
		:return:
		"""
		username = SuperManager.getInstance().configManager.getAliceConfigByName('githubUsername')
		token = SuperManager.getInstance().configManager.getAliceConfigByName('githubToken')
		return (username, token) if (username and token) else None


	@classmethod
	def hasAuth(cls) -> bool:
		"""
		Returns if the user has entered the github data for authentification
		:return:
		"""
		return cls.getGithubAuth() is not None


	def clone(self, skillName: str) -> bool:
		"""
		Clone a skill from github to the skills folder
		This will stash and clean all changes that have been made locally
		:param skillName:
		:return:
		"""
		if not self._dest.exists():
			self._dest.mkdir(parents=True)
		else:
			if Path(self._dest / '.git').exists():
				self.Commons.runSystemCommand(['git', '-C', str(self._dest), 'stash'])
				self.Commons.runSystemCommand(['git', '-C', str(self._dest), 'clean', '-df'])
			else:
				shutil.rmtree(str(self._dest))
				self._dest.mkdir(parents=True)

		return self._doClone(skillName)


	def _doClone(self, skillName: str) -> bool:
		"""
		internal method to perform the clone of a skill - assumes there are no pending changes
		:param skillName:
		:return:
		"""
		try:
			updateTag = self.SkillStoreManager.getSkillUpdateTag(skillName)
			try:
				if self.repo:
					pass
			except NotGitRepository as e:
				self.init()
			self.pull()

			self.Commons.runSystemCommand(['git', '-C', str(self._dest), 'checkout', updateTag])
			self.Commons.runSystemCommand(['git', '-C', str(self._dest), 'pull', 'origin', updateTag])

			return True
		except Exception as e:
			self.logWarning(f'Something went wrong cloning github repo: {e}')
			return False


	def checkOwnRepoAvailable(self, skillName: str) -> bool:
		"""
		check if a repository for the given skill name exists in the users github
		:param skillName:
		:return:
		"""
		req = requests.get(f'https://api.github.com/repos/{self.getGithubAuth()[0]}/skill_{skillName}', auth=GithubCloner.getGithubAuth())
		if req.status_code != 200:
			self.logInfo("Couldn't find repository on github")
			return False
		return True


	def createForkForSkill(self, skillName: str) -> bool:
		"""
		create a fork of the skill from alice official github to the users github.
		:param skillName:
		:return:
		"""
		data = {
			'owner': self.ConfigManager.getAliceConfigByName("githubUsername"),
			'repo' : f'skill_{skillName}'
		}
		req = requests.post(f'https://api.github.com/repos/project-alice-assistant/skill_{skillName}/forks', data=json.dumps(data), auth=GithubCloner.getGithubAuth())
		if req.status_code == 404:
			self.createRepo(aliceSK=True)
		if req.status_code != 202:
			self.logError(f'Couldn\'t create fork for repository! {req.status_code}')


	def checkoutOwnFork(self, skillName: str) -> bool:
		"""
		Assumes there is already a fork for the current skill on the users repository.
		Clone that repository, set upstream to the original repository.
		Will only work on master!
		:param skillName:
		:return:
		"""
		try:
			if not Path(self._dest / '.git').exists():
				self.Commons.runSystemCommand(['git', '-C', str(self._dest), 'init'])
				self.Commons.runSystemCommand(['git', '-C', str(self._dest), 'remote', 'add', 'origin', self._baseUrl])
				self.Commons.runSystemCommand(['git', '-C', str(self._dest), 'pull'])

			remote = self.getRemote()
			self.Commons.runSystemCommand(['git', '-C', str(self._dest), 'remote', 'add', 'AliceSK', remote])
			self.Commons.runSystemCommand(['git', '-C', str(self._dest), 'checkout', 'master'])
			self.Commons.runSystemCommand(['git', '-C', str(self._dest), 'branch', '--set-upstream-to=AliceSK/master'])
			self.Commons.runSystemCommand(['git', '-C', str(self._dest), 'pull'])

			return True
		except Exception as e:
			self.logWarning(f'Something went wrong cloning github repo: {e}')
			return False


	def getRemote(self, AliceSK:bool=False, origin:bool=False, noToken:bool=False):
		tokenPrefix = f'{self.ConfigManager.getAliceConfigByName("githubUsername")}:{self.ConfigManager.getAliceConfigByName("githubToken")}@'
		if self._skillName:
			if AliceSK:
				return f'https://{"" if noToken else tokenPrefix}github.com/{self.ConfigManager.getAliceConfigByName("githubUsername")}/skill_{self._skillName}.git'
			elif origin:
				return f'https://{"" if noToken else tokenPrefix}github.com/project-alice-assistant/skill_{self._skillName}.git'
			elif self._modified:
				return self.getRemote(AliceSK=True)
			else:
				return self.getRemote(origin=True)
		else:
			raise Exception("Skillname not set. Can't find git remote!")

	def checkRemote(self, AliceSK:bool=False, origin:bool=False):
		req = requests.get(self.getRemote(AliceSK=AliceSK, origin=origin), auth=GithubCloner.getGithubAuth())
		if req.status_code != 200:
			return False
		return True

	def checkoutMaster(self) -> bool:
		"""
		set upstream to origin/master
		:param skillName:
		:return:
		"""
		try:
			self.Commons.runSystemCommand(['git', '-C', str(self._dest), 'branch', '--set-upstream-to=origin/master'])
			return True
		except Exception as e:
			self.logWarning(f'Something went wrong cloning github repo: {e}')
			return False


	def gitDefaults(self) -> bool:
		try:
			self.Commons.runSystemCommand(['git', '-C', str(self._dest), 'config', 'user.email', self.ConfigManager.getAliceConfigByName('githubMail') or 'githubbot@projectalice.io'])
			self.Commons.runSystemCommand(['git', '-C', str(self._dest), 'config', 'user.name', self.ConfigManager.getAliceConfigByName('githubUsername') or 'ProjectAliceBot'])
			return True
		except Exception as e:
			self.logWarning(f'Something went wrong cloning github repo: {e}')
			return False


	@property
	def repo(self):
		if self._repo:
			return self._repo
		self._repo = Repo(f'skills/{self._skillName}')
		return self._repo


	@repo.setter
	def repo(self, repo: Repo):
		self._repo = repo


	def pull(self):
		pull(repo=self.repo, remote_location=self.getRemote(), refspecs=b'master')


	def getPath(self):
		return Path(f'skills/{self._skillName}')


	def init(self) -> bool:
		"""
		create a repository online and clone it to the skills folder - only afterwards fill it with files by AliceSK
		:return:
		"""
		data = {
			'name'       : f'skill_{self._skillName}',
			'description': 'Bout Fritz!Box',
			'has-issues' : True,
			'has-wiki'   : False
		}
		req = requests.post('https://api.github.com/user/repos', data=json.dumps(data), auth=GithubCloner.getGithubAuth())

		if req.status_code != 201:
			raise Exception("Couldn't create the repository on Github")

		clone(source=self.getRemote(), target=f'skills/{self._skillName}')

		self.repo = Repo.init(f'skills/{self._skillName}')
		remote_add(repo=self.repo, name=f'AliceSK', url=self.getRemote())


	def add(self) -> bool:
		"""
		add all changes to the current tree
		:return:
		"""
		stat = status(self.repo)
		self.repo.stage(stat.unstaged + stat.untracked)
		return True


	def commit(self, message : str = "pushed by AliceSK") -> bool:
		"""
		commit the current changes for that skill
		:param message:
		:return:
		"""
		commit(repo=self.repo, message=message)
		return True


	def push(self) -> bool:
		"""
		push the skills changes to AliceSK upstream
		:return:
		"""
		push(repo=self.repo, remote_location=self.getRemote(), refspecs=b"master")
		return True


	def isRepo(self) -> bool:
		"""
		check if the skills folder is already a repository
		:return:
		"""
		try:
			self.repo
			return True
		except NotGitRepository as e:
			self.logInfo(e)
			return False

	def createRepo(self, aliceSK: bool = False) -> bool:
		"""
		create a repository and set the remotes for origin and AliceSK
		:return:
		"""
		if not self.isRepo():
			self.repo = Repo.init(self.getPath())
		try:
			self.createRemote()
		except Exception:
			return False
		try:
			remote_add(repo=self.repo, name=b"origin", url=self.getRemote(origin=True))
		except RemoteExists:
			pass
		try:
			if aliceSK:
				remote_add(repo=self.repo, name=b"AliceSK", url=self.getRemote(AliceSK=True))
		except RemoteExists:
			pass
		return True

	def createRemote(self) -> bool:
		"""
		create the remote repository for the current user
		:return:
		"""
		data = {
			'name'       : f'skill_{self._skillName}',
			'description': "test",
			'has-issues' : True,
			'has-wiki'   : False
		}
		req = requests.post('https://api.github.com/user/repos', data=json.dumps(data), auth=GithubCloner.getGithubAuth())

		if req.status_code != 201:
			raise Exception("Couldn't create the repository on Github")

	def gitDoMytest(self):
		skillName = 'FritzBox'
		rep : Repo = Repo(f'skills/{skillName}')
		self.logInfo(f'got {rep} in {rep.path}')

		stat = status(rep)
		self.logInfo(f'statstaged {stat.staged}')
		self.logInfo(f'statuntrack {stat.untracked}')
		self.logInfo(f'statunstag {stat.unstaged}')
		rep.stage(stat.unstaged + stat.untracked)
		self.logInfo(f'commit {commit(repo=rep, message="pushed by AliceSK")}')
		self.logInfo(f'push {push(repo=rep, remote_location=self.getRemote(), refspecs=b"master")}')
