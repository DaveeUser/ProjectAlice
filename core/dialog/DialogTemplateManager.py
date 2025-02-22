#  Copyright (c) 2021
#
#  This file, DialogTemplateManager.py, is part of Project Alice.
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
#  Last modified: 2021.04.13 at 12:56:46 CEST

import json
from pathlib import Path
from typing import Dict, Generator, List, Optional

from core.base.SuperManager import SuperManager
from core.base.model.Manager import Manager
from core.commons import constants
from core.dialog.model.DialogSession import DialogSession
from core.dialog.model.DialogTemplate import DialogTemplate


class DialogTemplateManager(Manager):

	def __init__(self):
		super().__init__()

		self._pathToCache = Path(self.Commons.rootDir(), 'var/cache/dialogTemplates/')
		self._pathToCache.mkdir(parents=True, exist_ok=True)

		self._pathToChecksums = self._pathToCache / f'checksums{constants.JSON_EXT}'
		self._pathToData = self._pathToCache / f'data{constants.JSON_EXT}'

		if not self._pathToChecksums.exists():
			self._pathToChecksums.write_text('{}')

		if not self._pathToData.exists():
			self._pathToData.write_text('{}')

		self._dialogTemplates: Optional[Dict[str, DialogTemplate]] = None
		self._slotTypes: Optional[Dict[str, List[DialogTemplate]]] = None
		self._intentsToSkills: Optional[Dict[str, DialogTemplate]] = None


	@property
	def pathToData(self) -> Path:
		return self._pathToData


	def initHolders(self):
		self._dialogTemplates = dict()
		self._slotTypes = dict()
		self._intentsToSkills = dict()


	def onStart(self):
		super().onStart()
		self._loadData()


	def checkData(self) -> bool:
		uptodate = self.checkCache()
		if uptodate:
			self.logInfo('Cache uptodate')

		return uptodate


	def train(self):
		self._loadData()
		self.buildCache()


	def _loadData(self):
		self.initHolders()

		for resource in self.skillResource():
			data = json.loads(resource.read_text())
			dialogTemplate = DialogTemplate(**data)

			# If we have an utterance extender, apply it
			extender = Path(resource.parent, resource.stem).with_suffix(f'.ext{constants.JSON_EXT}')
			if extender.exists():
				dialogTemplate.addUtterancesExtender(extender)

			self._dialogTemplates[dialogTemplate.skill] = dialogTemplate

			# Generate a list of slots with skills using it
			for slot in dialogTemplate.allSlots:
				self._slotTypes.setdefault(slot.name, list()).append(dialogTemplate)

			# Keep track of what skill has what intents
			for intent in dialogTemplate.allIntents:
				self._intentsToSkills[intent.name] = dialogTemplate

		self._checkSlotExtenders()


	def _checkSlotExtenders(self):
		for slotName, templates in self._slotTypes.items():
			if len(templates) <= 1:
				continue

			baseTemplate = templates.pop(0)
			for template in templates:
				self.logInfo(f'Skill **{template.skill}** extends slot **{slotName}**')
				baseTemplate.fuseSlotType(template, slotName)


	def _dumpData(self):
		data = list()
		for skillName, skillData in self._dialogTemplates.items():
			data.append(skillData.dump())

		self._pathToData.write_text(data=json.dumps(data, ensure_ascii=False))


	def checkCache(self) -> bool:
		with self._pathToChecksums.open() as fp:
			checksums = json.load(fp)

		uptodate = True
		# First check upon the skills that are installed and active
		language = self.LanguageManager.activeLanguage
		for skillName, skillInstance in self.SkillManager.allWorkingSkills.items():

			self.logInfo(f'Checking data for skill **{skillName}**')
			if skillName not in checksums:
				self.logInfo(f'Skill **{skillName}** is new')
				checksums[skillName] = list()
				uptodate = False
				continue

			pathToResources = skillInstance.getResource('dialogTemplate')
			if not pathToResources.exists():
				self.logWarning(f'**{skillName}** has no dialog template defined')
				continue

			for file in pathToResources.glob(f'*{constants.JSON_EXT}'):
				filename = file.stem
				if filename not in checksums[skillName]:
					# Trigger a change only if the change concerns the language in use
					if filename == language:
						self.logInfo(f'Skill **{skillName}** has new language support **{filename}**')
						uptodate = False
					elif '.ext' in filename and filename.replace('.ext', '') == language:
						self.logInfo(f'Skill **{skillName}** has a new utterance extender **{filename}**')
						uptodate = False
					continue

				if self.Commons.fileChecksum(file) != checksums[skillName][filename] and (filename == language or filename.replace('.ext', '') == language):
					# Trigger a change only if the change concerns the language in use
					self.logInfo(f'Skill **{skillName}** has changes in language **{filename}**')
					uptodate = False

		# Now check that what we have in cache in actually existing and wasn't manually deleted
		for skillName, languages in checksums.items():
			if not Path(self.Commons.rootDir(), f'skills/{skillName}/').exists():
				self.logInfo(f'Skill **{skillName}** was removed')
				uptodate = False
				break

			for lang in languages:
				if not Path(self.Commons.rootDir(), f'skills/{skillName}/dialogTemplate/{lang}{constants.JSON_EXT}').exists() and lang == language:
					if '.ext' in lang:
						self.logInfo(f'Skill **{skillName}** has dropped utterance extender in **{lang}**')
					else:
						self.logInfo(f'Skill **{skillName}** has dropped language **{lang}**')
					uptodate = False

		return uptodate


	def buildCache(self):
		self.logInfo('Building dialog templates cache')

		self._dumpData()

		cached = dict()

		for skillName, skillInstance in self.SkillManager.allWorkingSkills.items():
			pathToResources = skillInstance.getResource('dialogTemplate')
			if not pathToResources.exists():
				self.logWarning(f'**{skillName}** has no dialog template defined to build cache')
				continue

			cached[skillName] = dict()
			for file in pathToResources.glob(f'*{constants.JSON_EXT}'):
				cached[skillName][file.stem] = self.Commons.fileChecksum(file)

		self._pathToChecksums.write_text(json.dumps(cached, indent='\t', sort_keys=True))


	def cleanCache(self, skillName: str):
		for file in Path(self._pathToCache, 'trainingData').glob(f'*{constants.JSON_EXT}'):
			if file.stem.startswith(f'{skillName}_'):
				file.unlink()

		checksums = json.loads(self._pathToChecksums.read_text())
		checksums.pop(skillName, None)

		self._pathToChecksums.write_text(json.dumps(checksums, indent='\t', sort_keys=True))


	def clearCache(self, rebuild: bool = True):
		if self._pathToChecksums.exists():
			self._pathToChecksums.write_text('{}')
			self.logInfo('Cache cleared')

		if rebuild:
			self.buildCache()


	def addUtterance(self, session: DialogSession):
		text = session.previousInput
		if not text:
			return

		intent = session.secondLastIntent
		if not intent:
			return

		if '/' in intent:
			intent = intent.split('/')[-1]

		if not intent in self._intentsToSkills:
			return

		dialogTemplate = self._intentsToSkills[intent]
		skill = self.SkillManager.getSkillInstance(skillName=dialogTemplate.skill)
		if not skill:
			return

		skill.addUtterance(text=text, intent=intent)
		self.DialogManager.cleanNotRecognizedIntent(text=text)
		self.ThreadManager.doLater(interval=2, func=self.AssistantManager.checkAssistant)


	@classmethod
	def skillResource(cls) -> Generator[Path, None, None]:
		languageManager = SuperManager.getInstance().languageManager
		skillManager = SuperManager.getInstance().skillManager

		if not languageManager or not skillManager:
			return

		language = languageManager.activeLanguage
		for skillName, skillInstance in skillManager.allWorkingSkills.items():
			resource = skillInstance.getResource(f'dialogTemplate/{language}{constants.JSON_EXT}')
			if not resource.exists():
				continue

			yield resource
