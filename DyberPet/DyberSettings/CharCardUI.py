#coding:utf-8
import os
import json
from datetime import datetime
from shutil import copytree, rmtree
from pathlib import Path
import subprocess

from qfluentwidgets import (ScrollArea, ExpandLayout, SettingCardGroup, InfoBar, FlowLayout,
                            PushSettingCard, PushButton, RoundMenu, Action, MessageBox,
                            InfoBarPosition, HyperlinkButton, ToolButton, PushButton, setFont,
                            StateToolTip, TransparentPushButton, TransparentToolButton)

from qfluentwidgets import FluentIcon as FIF

from PySide6.QtCore import Qt, QThread, Signal, QUrl, QStandardPaths, QSize
from PySide6.QtGui import QDesktopServices, QIcon, QFont
from PySide6.QtWidgets import QWidget, QLabel, QApplication, QFileDialog, QInputDialog, QCheckBox, QSizePolicy, QHBoxLayout, QSpacerItem, QMessageBox

from .custom_utils import CharCard, CharCardGroup, CharLine
from DyberPet.conf import CheckCharFiles
import DyberPet.settings as settings

from sys import platform

basedir = settings.BASEDIR
module_path = os.path.join(basedir, 'DyberPet/DyberSettings/')


class CharInterface(ScrollArea):
    """ Character Management interface """
    change_pet = Signal(str, name='change_pet')

    def __init__(self, sizeHintDyber, parent=None):
        super().__init__(parent=parent)
        self.setObjectName("CharInterface")
        self.newPetFolder = None
        self.thread = None
        self.chibiThread = None
        self.stateTooltip = None
        self.launchTooltip = None
        self.sizeHintDyber = (sizeHintDyber[0]-100, sizeHintDyber[1])

        self.scrollWidget = QWidget()
        self.expandLayout = ExpandLayout(self.scrollWidget)

        # Title label
        self.panelLabel = QLabel(self.tr("Characters Management"), self)
        self.panelLabel.setSizePolicy(QSizePolicy.Maximum, self.panelLabel.sizePolicy().verticalPolicy())
        self.panelLabel.adjustSize()
        self.panelHelp = TransparentToolButton(QIcon(os.path.join(basedir, 'res/icons/question.svg')))
        self.panelHelp.setFixedSize(25,25)
        self.panelHelp.setIconSize(QSize(25,25))

        self.titleWidget = QWidget(self)
        self.titleWidget.setFixedWidth(sizeHintDyber[0]-165)
        self.titleLayout = QHBoxLayout(self.titleWidget)
        self.titleLayout.setContentsMargins(0, 0, 0, 0)
        self.titleLayout.setSpacing(0)

        self.titleLayout.addWidget(self.panelLabel, Qt.AlignLeft | Qt.AlignVCenter)
        spacerItem1 = QSpacerItem(10, 20, QSizePolicy.Fixed, QSizePolicy.Minimum)
        self.titleLayout.addItem(spacerItem1)
        self.titleLayout.addWidget(self.panelHelp, Qt.AlignLeft | Qt.AlignVCenter)
        spacerItem2 = QSpacerItem(10, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.titleLayout.addItem(spacerItem2)

        # HyperLink to character collection (website not implemented yet)
        self.CharListLink = HyperlinkButton(
                                            settings.CHARCOLLECT_LINK, 
                                            self.tr('Collected Characters'), 
                                            self, FIF.LINK)
        self.CharListLink.setSizePolicy(QSizePolicy.Maximum, self.CharListLink.sizePolicy().verticalPolicy())
        
        # Button to add chars from local file
        self.addButton = PushButton(self.tr("Add Characters"), self, FIF.ADD)
        self.addButton.setSizePolicy(QSizePolicy.Maximum, self.addButton.sizePolicy().verticalPolicy())
        self.addButton.setToolTip("支持 DyberPet 模组、Codex Pets 图集和透明 GIF/PNG 动画文件夹")
        self.quickStartButton = PushButton(self.tr("快速选桌宠"), self, FIF.HEART)
        self.quickStartButton.setToolTip(self.tr("搜索本机可播放角色、预览动作并立即切换"))
        self.showDemoRoles = QCheckBox(self.tr("显示低保真演示"), self)
        self.showDemoRoles.setChecked(False)
        self.showDemoRoles.setToolTip(self.tr("仅供开发与演示，不代表角色原设；默认不推荐"))
        self.titleLayout.addWidget(self.showDemoRoles, Qt.AlignRight | Qt.AlignVCenter)
        self.titleLayout.addWidget(self.CharListLink, Qt.AlignRight | Qt.AlignVCenter)
        self.catalogButton = PushButton(self.tr("全部角色库"), self, FIF.SEARCH)
        self.catalogButton.setToolTip(
            self.tr("按中文/英文搜索 125 个角色，筛选原创演示和个人素材；不自动下载"))
        self.artistSourceButton = PushButton(self.tr("安装作者原画角色"), self, FIF.DOWNLOAD)
        self.artistSourceButton.setToolTip(
            self.tr("从公开作者作品本机安装原有逐帧动画、Codex 图集和 Shimeji 动作，不生成替代造型"))
        self.mascotButton = PushButton(self.tr("咕嘎 / Doro"), self, FIF.HEART)
        self.mascotButton.setToolTip(
            self.tr("查看企鹅/四足演示角色以及个人导入的对应素材；不冒充作者原设美术"))

        # Button to show instructions on how to manually add chars
        #self.instructButton = TransparentPushButton(self.tr("Add Chars Manually"), self, FIF.QUESTION)
        #self.instructButton.setSizePolicy(QSizePolicy.Maximum, self.instructButton.sizePolicy().verticalPolicy())

        self.headerWidget = QWidget(self)
        self.headerWidget.setFixedWidth(sizeHintDyber[0]-165)
        self.headerLayout = QHBoxLayout(self.headerWidget)
        self.headerLayout.setContentsMargins(0, 0, 0, 0)
        self.headerLayout.setSpacing(0)

        self.headerLayout.addWidget(self.addButton, Qt.AlignLeft | Qt.AlignVCenter)
        self.headerLayout.addWidget(self.quickStartButton, Qt.AlignLeft | Qt.AlignVCenter)
        self.headerLayout.addWidget(self.catalogButton, Qt.AlignLeft | Qt.AlignVCenter)
        self.headerLayout.addWidget(self.artistSourceButton, Qt.AlignLeft | Qt.AlignVCenter)
        self.headerLayout.addWidget(self.mascotButton, Qt.AlignLeft | Qt.AlignVCenter)
        spacerItem1 = QSpacerItem(10, 20, QSizePolicy.Fixed, QSizePolicy.Minimum)
        self.headerLayout.addItem(spacerItem1)
        #spacerItem2 = QSpacerItem(15, 20, QSizePolicy.Fixed, QSizePolicy.Minimum)
        #self.headerLayout.addItem(spacerItem2)
        #self.headerLayout.addWidget(self.instructButton, Qt.AlignLeft | Qt.AlignVCenter)
        spacerItem3 = QSpacerItem(15, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.headerLayout.addItem(spacerItem3)
        

        self.__initCardLayout()

        self.__initWidget()

    @staticmethod
    def _isLowFidelityDemo(role):
        path = Path(basedir) / "res" / "role" / role
        return (path / "BUILTIN_CHIBI_DEMO.json").is_file() or (
            path / "BUILTIN_MASCOT_DEMO.json").is_file()

    def _applyDemoRoleVisibility(self):
        enabled = self.showDemoRoles.isChecked()
        # Never hide a currently active legacy character: existing users
        # should still be able to see and manage their selected pet.
        for line in self.CharLineList:
            role = getattr(line, "chrFolder", None)
            if role is None:
                role = getattr(line, "petFolder", None)
            if isinstance(role, str):
                line.setVisible(enabled or not self._isLowFidelityDemo(role)
                                or role == settings.petname)

    def __initCardLayout(self):

        self.CharCardGroup = CharCardGroup(
            self.tr("Characters"), self.sizeHintDyber, self.scrollWidget)

        self.CharCardList = []
        self.CharLineList = []
        petlist = settings.pets.copy()
        petlist.sort()
        for i, character in enumerate(petlist):
            
            infoLine = CharLine(i, chrFolder=character, parent=self.CharCardGroup)
            self.CharCardGroup.addInfoCard(infoLine)
            self.CharLineList.append(infoLine)
            
            
            infoFile = os.path.join(basedir,"res/role", character, "info/info.json")
            if not os.path.exists(infoFile):
                self.CharCardList.append(None)
            else:
                card = CharCard(i, jsonPath=infoFile, petFolder=character) #, parent=self.CharCardGroup)
                self.CharCardList.append(card)



    def __initWidget(self):
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setViewportMargins(0, 120, 0, 20)
        self.setWidget(self.scrollWidget)
        self.setWidgetResizable(True)

        # initialize style sheet
        self.__setQss()

        # initialize layout
        self.__initLayout()
        self.__connectSignalToSlot()

    def __initLayout(self):
        self.titleWidget.move(50, 20)
        self.headerWidget.move(55, 75)
 
        # add setting card group to layout
        self.expandLayout.setSpacing(28)
        self.expandLayout.setContentsMargins(60, 10, 60, 0)
        self.expandLayout.addWidget(self.CharCardGroup)


    def __setQss(self):
        """ set style sheet """
        self.scrollWidget.setObjectName('scrollWidget')
        self.panelLabel.setObjectName('settingLabel')

        theme = 'light' #if isDarkTheme() else 'light'
        with open(os.path.join(basedir, 'res/icons/system/qss', theme, 'setting_interface.qss'), encoding='utf-8') as f:
            self.setStyleSheet(f.read())

        #setFont(self.panelLabel, 33, QFont.Bold)

    def __connectSignalToSlot(self):
        """ connect signal to slot """
        
        for i, charCard in enumerate(self.CharCardList):
            self.CharLineList[i].launchClicked.connect(self.__onLaunchClicked)

            if charCard:
                self.CharLineList[i].infoClicked.connect(self.__onInfoClicked)
        
                self.CharCardList[i].card.gotoClicked.connect(self.__onGotoClicked)
                self.CharCardList[i].card.deleteClicked.connect(self.__onDeleteClicked)

        self.addButton.clicked.connect(self.__onAddClicked)
        self.quickStartButton.clicked.connect(self._showQuickStartGuide)
        self.catalogButton.clicked.connect(self._showAllCharacterCatalog)
        self.showDemoRoles.toggled.connect(self._applyDemoRoleVisibility)
        self._applyDemoRoleVisibility()
        self.artistSourceButton.clicked.connect(self._installArtistGenshin)
        self.mascotButton.clicked.connect(self._showMascotLibrary)
        self.panelHelp.clicked.connect(self.__onShowInstruction)

    def __onLaunchClicked(self, petname):
        # Ignore if it's current char
        if settings.petname == petname:
            settings.default_pet = petname
            settings.save_settings()
            return True
        # Confirm
        title = self.tr('Switch to ') + petname + "?"
        content = self.tr("Might take some time, just wait a moment <3")
        if not self.__showMessageBox(title, content):
            return False

        self._launchStateTooltip()
        self.change_pet.emit(petname)
        # Switching in the GUI should survive restart.
        settings.default_pet = petname
        settings.save_settings()
        return True

    def _launchStateTooltip(self):
        self.launchTooltip = StateToolTip(
            self.tr('Loading Character...'), self.tr('Please wait patiently'), self.window())
        self.launchTooltip.move(self.launchTooltip.getSuitablePos())
        self.launchTooltip.show()

    def _finishStateTooltip(self):
        if not self.launchTooltip:
            return
        else:
            self.launchTooltip.setContent(
                self.tr('Launched!') + ' 😆')
            self.launchTooltip.setState(True)
            self.launchTooltip = None

    def __onGotoClicked(self, folder):
        if platform == 'win32':
            os.startfile(os.path.normpath(folder))
        elif platform == "darwin":
            subprocess.call(["open", os.path.normpath(folder)])
        else:
            # For Linux - not tested
            subprocess.call(["xdg-open", os.path.normpath(folder)])

    def __onDeleteClicked(self, cardIndex, folder):
        # Judge if it is current pet

        # Move file to trash bin

        # Remove char from settings.pet

        # Update basicSetting change pet

        # Delete character List and Card
        title = self.tr("Function incomplete")
        content = self.tr("The function has not been implemented yet.\nCurrently, you can Go To Folder, delete the whole folder, and restart App.\nSorry for the inconvenience.")
        #if not self.__showMessageBox(title, content):
        #    return
        yesText = self.tr("Go to Folder")
        if self.__showMessageBox(title, content, yesText):
            resFolder = os.path.join(basedir, 'res/role')

            if platform == 'win32':
                os.startfile(os.path.normpath(resFolder))
            elif platform == "darwin":
                subprocess.call(["open", os.path.normpath(resFolder)])
            else:
                # For Linux - not tested
                subprocess.call(["xdg-open", os.path.normpath(resFolder)])
        else:
            return


    def __onInfoClicked(self, cardIndex, pos):
        if self.CharCardList[cardIndex].isVisible():
            self.CharCardList[cardIndex].hide()
        else:
            self.CharCardList[cardIndex].move(pos)
            self.CharCardList[cardIndex].show()

    def __onAddClicked(self):
        # Confirm
        title = self.tr("Adding Character")
        content = self.tr("仅将您选择的角色素材导入这台电脑，不会自动联网下载或发布角色包。请确认文件来源可信，并自行检查创作者对个人使用、修改及分享的具体要求。安装不代表作品身份或授权已经验证；已有角色不会被覆盖。")
        if not self.__showMessageBox(title, content):
            return

        # Keep existing role management layout: one compact choice determines
        # whether user selects an unpacked role folder or a native MOD ZIP.
        from tools.install_pinned_codexpetdb import listed_packages
        verified_source_count = len(listed_packages()["sources"])
        options = ["个人本地导入：角色文件夹 / Codex / GIF / PNG", "个人本地导入：原生角色 ZIP",
                   "生成原创 Q 版示例角色（不需下载素材）",
                   "浏览角色合集来源（网页手动获取，不自动下载）",
                    "个人本地导入：Shimeji 原画 ZIP（仅提取图片）",
                    "个人本地导入：Codex 动画 ZIP（仅提取图集）",
                     "个人本地导入：React-Shimeji 完整图集 TS（先校验 LFS）",
                     f"个人使用：下载 SHA-256 固定的{verified_source_count}位原神角色原画 ZIP",
                     "个人本地导入：已下载的 SHA-256 固定原画 ZIP（断网可用）"]
        choice, accepted = QInputDialog.getItem(
            self, self.tr("添加角色"), self.tr("请选择本地素材类型："),
            options, 0, False
        )
        if not accepted:
            return
        docs = QStandardPaths.locate(
            QStandardPaths.DocumentsLocation, '',
            QStandardPaths.LocateDirectory
        )
        if choice == options[1]:
            archive, _ = QFileDialog.getOpenFileName(
                self, self.tr("请选择 DyberPet 原生角色 ZIP"), docs,
                "ZIP Archive (*.zip)"
            )
            if archive:
                self._importNativeZip(archive)
            return
        if choice == options[2]:
            self._importOriginalDemo()
            return
        if choice == options[7]:
            self._importPinnedPetDb()
            return
        if choice == options[8]:
            self._importPinnedPetDb(local_archive=True)
            return
        if choice == options[6]:
            module, _ = QFileDialog.getOpenFileName(
                self, self.tr("请选择已下载的完整 React-Shimeji LFS 模块"),
                docs, "React-Shimeji Module (*.ts)")
            if module:
                self._importReactShimeji(module)
            return
        if choice == options[5]:
            archive, _ = QFileDialog.getOpenFileName(
                self, self.tr("请选择本人已下载的 Codex 动画 ZIP"), docs,
                "Codex Pet ZIP (*.zip)")
            if archive:
                self._importCodexZip(archive)
            return
        if choice == options[4]:
            archive, _ = QFileDialog.getOpenFileName(
                self, self.tr("请选择本人已下载的标准 Shimeji ZIP"), docs,
                "Shimeji ZIP (*.zip)")
            if archive:
                self._importShimejiZip(archive)
            return
        if choice == options[3]:
            QDesktopServices.openUrl(QUrl(
                "https://github.com/clonetimer/DyberPet/blob/main/docs/collection.md"))
            return
        folder = QFileDialog.getExistingDirectory(
            self, self.tr("Please select the character folder"), docs)

        # If no file selected
        if not folder:
            return
        else:
            print(folder)
            #return

        # Codex Pets folders can be imported with the same button; no layout changes.
        # Only folders containing a Codex manifest (not standard DyberPet config)
        # are passed through the optional sprite converter.
        if (os.path.isfile(os.path.join(folder, "pet.json")) and
                not os.path.isfile(os.path.join(folder, "pet_conf.json"))):
            self._importCodexCharacter(folder)
            return

        # Generic local animations are handled through the same button. We
        # only select folders with a recognizable idle animation, not arbitrary
        # user documents; existing DyberPet modules keep their current path.
        local_files = set(os.listdir(folder))
        has_idle_animation = (
            any(item.lower() in {"idle.gif", "idle.png", "idle.webp",
                                 "stand.gif", "stand.png", "stand.webp"}
                for item in local_files) or
            any(item.lower().startswith(("idle_", "stand_")) and
                item.lower().endswith((".png", ".gif", ".webp"))
                for item in local_files)
        )
        if has_idle_animation and not os.path.isfile(os.path.join(folder, "pet_conf.json")):
            self._importLocalChibi(folder, mode="animations")
            return

        # Early GenshinImpact distributions already contain res/role/<name>.
        # Use the same safe worker staging/validation as the native ZIP path;
        # do not copy untrusted extracted folders directly into the live tree.
        if (os.path.isfile(os.path.join(folder, "pet_conf.json")) and
                os.path.isfile(os.path.join(folder, "act_conf.json"))):
            self._importNativeFolder(folder)
            return

        # Check files integrity
        statCode, errorList = CheckCharFiles(os.path.abspath(folder))
        if 0 < statCode < 7:
            self._send_CharImportResult(statCode, errorList)
            return
        elif statCode >=7:
            statCode -= 6
            self._send_itemImportResult(statCode, errorList)
            return

        # Copy file to res/role
        petFolder = os.path.basename(folder)
        destinationFolder = os.path.join(basedir, 'res/role', petFolder)
        #status = 
        # Check if char with the same name exist
        if os.path.exists(destinationFolder):
            content = self.tr("There is already a character with the same name added.")
            self.__showSystemNote(content, 2)
            return 0
        self.newPetFolder = petFolder
        self._importChar(folder, destinationFolder)
        #if not status:
        #    return
        #return


    def _showMascotLibrary(self, selected_kind=None):
        """Actual local mascot status; never mistake generated art for source."""
        from tools.mascot_library import scan_mascot_library
        try:
            report=scan_mascot_library(Path(basedir)/"res"/"role")
        except (ValueError,OSError) as exc:
            self.__showSystemNote(self.tr("咕嘎 / Doro 角色库读取失败：")+str(exc),2)
            return
        names={}
        for entry in report["mascots"]:
            actual=len(entry["imported_creator_art"])
            demos=len(entry["original_demos"])
            name=("咕嘎 Guga" if entry["key"]=="guga" else "Doro 四足宠物")
            label=f"{name} · 原创演示 {demos} / 个人来源导入 {actual}"
            names[label]=entry
        install_actions={
            "【联网安装】咕嘎作者公开图集（个人本地使用）":"guga",
            "【联网安装】Doro 二创作者图集（CC BY-NC，本机使用）":"doro",
        }
        if selected_kind in ("guga", "doro"):
            # The all-character catalogue already resolved the chosen mascot.
            # Keep the original independent picker for consent-driven downloads.
            entry=next(item for item in report["mascots"]
                       if item["key"]==selected_kind)
        else:
            chosen,accepted=QInputDialog.getItem(
                self,self.tr("咕嘎 / Doro 独立角色库"),
                self.tr("原创演示不是 CIRCUS/legeling 作者的原画或原声。"),
                list(install_actions)+list(names),0,False)
            if not accepted:
                return
            if chosen in install_actions:
                self._installCreatorMascot(install_actions[chosen])
                return
            if chosen not in names:
                return
            entry=names[chosen]
        roles=entry["imported_creator_art"]+entry["original_demos"]
        if not roles:
            self.__showMessageBox(self.tr("尚无角色动画"),
                                  self.tr("请通过「添加角色」导入本地 Codex/PNG 素材。"))
            return
        options={}
        for row in roles:
            provenance=("个人导入的作者公开图集 · 原设需人工核对"
                        if row in entry["imported_creator_art"]
                        else "程序原创演示 · 非原作者的图和声音")
            options[
                f"{row['folder']} · {row['actions']} 类动作 / "
                f"{row['frames']} 帧 · {provenance}"]=row
        if len(options)==1:
            role=roles[0]
        else:
            choice,ok=QInputDialog.getItem(
                self,self.tr("选择桌宠素材"),
                self.tr("优先查看个人导入的角色，也可以继续使用内置原创演示："),
                list(options),0,False)
            if not ok or choice not in options:
                return
            role=options[choice]
        name=role["folder"]
        folder=Path(basedir)/"res"/"role"/name
        if not folder.is_dir() or folder.is_symlink():
            self.__showSystemNote(self.tr("角色目录已丢失或不可安全读取。"),2)
            return
        operations=[
            "▶ 在界面中预览动画（可选择动作）",
            "✓ 使用这个角色作为桌宠",
            "↗ 查看本地素材目录",
        ]
        operation,ok=QInputDialog.getItem(
            self,self.tr("咕嘎 / Doro · 角色操作"),
            self.tr("请选择要进行的操作，预览不修改角色文件："),
            operations,0,False)
        if not ok:
            return
        if operation==operations[0]:
            from .mascot_preview_dialog import MascotActionPreview
            try:
                viewer=MascotActionPreview(
                    folder,original_demo=role in entry["original_demos"],
                    parent=self)
            except (ValueError,OSError,TypeError) as exc:
                self.__showSystemNote(self.tr("预览失败：")+str(exc),2)
                return
            viewer.exec()
        elif operation==operations[1]:
            if name not in settings.pets:
                self.__showSystemNote(
                    self.tr("角色存在于磁盘但尚未被当前桌宠会话加载，请重启 DyberPet。"),2)
                return
            self.__onLaunchClicked(name)
        elif operation==operations[2]:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder.resolve())))

    def _installCreatorMascot(self, kind):
        """One user-confirmed network fetch; all art remains local, not bundled."""
        if self.chibiThread is not None:
            return
        explanation = (
            "咕嘎图集由 CIRCUS 发布，来源页没有明确再分发许可；"
            "仅为你自己在本机获取并转换，请尊重创作者的后续使用条款。"
            if kind == "guga" else
            "Doro 图集为 legeling 发布的 CC BY-NC 4.0 二创；"
            "相关游戏人物的权利另行保留。仅下载本机试用，不含原声。"
        )
        if not self.__showMessageBox(
                self.tr("联网下载独立角色来源图集"),
                explanation + " 软件会校验固定版本 SHA-256，不会上传本机文件。确认获取？"):
            return
        self.addButton.setEnabled(False)
        self.chibiThread=ChibiImportThread(
            kind, os.path.join(basedir,"res","role"),
            mode="creator_source", profile=None, preset=kind, folder=None)
        self.chibiThread.done.connect(self._onChibiImportComplete)
        self.chibiThread.finished.connect(self._onChibiThreadFinished)
        self.chibiThread.start()
        self.__showSystemNote(self.tr("正在本机获取并校验角色作者发布的图集，然后转换动画。"),1)

    def _installArtistGenshin(self, only_profile=None):
        """Select genuine source art for one chosen role; never redraw it."""
        if not isinstance(only_profile, str) or not only_profile.startswith("genshin_"):
            only_profile = None
        if self.chibiThread is not None:
            self.__showSystemNote("其他角色安装仍在进行。", 1)
            return
        from tools.creator_art_preference import install_preference
        from tools.install_artist_genshin import ROLES, SOURCE_URL
        from tools.install_artist_codex import SOURCES, ROOT
        from tools.install_artist_shimeji import source_manifest
        from tools.install_nanopet_shimeji import source_manifest as nano_manifest
        from tools.install_external_codex import source_manifest as external_manifest
        from tools.install_pinned_codexpetdb import listed_packages, fixed_archive_url
        shimeji = source_manifest()
        nano = nano_manifest()
        external = external_manifest()
        petdb = listed_packages()["sources"]
        labels = {f"① 精细Q版优先 · 完整原生动画 · {title}":("artist_genshin", key)
                  for key, (_, _, title) in ROLES.items()}
        labels.update({f"② 作者图集待视觉核对 · {row[1]} · {key}":("artist_codex", key)
                       for key, row in SOURCES.items()})
        labels.update({f"③ 可接受小型 Shimeji · {row['name']} · {key}":("artist_shimeji", key)
                       for key, row in shimeji["roles"].items()})
        labels.update({f"③ 可接受小型 Shimeji · {row['name']} · {row['artist']}":("artist_nano", key)
                       for key, row in nano["roles"].items()})
        labels.update({f"② 独立画师图集待视觉核对 · {row['name']} · {key}":("artist_external_codex", key)
                       for key, row in external["sources"].items()})
        labels.update({
            f"② 已核验 SHA-256 的原画 ZIP · {row['slug']} · {key}": ("pinned_codexpetdb", key)
            for key, row in petdb.items()
        })
        if only_profile:
            def mapped_profile(source):
                mode, key = source
                if mode == "artist_genshin":
                    return ROLES[key][1]
                if mode == "artist_codex":
                    return SOURCES[key][2]
                if mode == "artist_shimeji":
                    return shimeji["roles"][key]["profile"]
                if mode == "artist_nano":
                    return nano["roles"][key]["profile"]
                if mode == "pinned_codexpetdb":
                    return petdb[key]["profile"]
                return external["sources"][key]["profile"]
            labels = {name: source for name, source in labels.items()
                      if mapped_profile(source) == only_profile}
        if not labels:
            self.__showMessageBox(
                "该角色暂缺原画资源",
                "目前尚未找到并固定校验属于此人物的公开作者动画。"
                "不会用简笔画、同名其他游戏角色或通用换色素材代替。"
                "此人物继续列入待补充清单。")
            return
        selected, ok = QInputDialog.getItem(
            self, "安装真实来源的桌宠美术",
            "第一组精细 Q 版优先；图集需看图复核；第二组 Shimeji 可接受。"
            "以下只是素材风格优先级，不代表原设相似度验收通过。",
            sorted(labels, key=lambda name: (install_preference(labels[name][0]), name)), 0, False)
        if not ok or selected not in labels:
            return
        mode, kind = labels[selected]
        if mode == "artist_genshin":
            source = SOURCE_URL + ROLES[kind][0]
        elif mode == "artist_codex":
            source = ROOT + "/" + SOURCES[kind][0]
        elif mode == "artist_shimeji":
            source = ("https://github.com/" + shimeji["repository"]
                      + "/tree/" + shimeji["revision"]
                      + "/public/assets/" + kind)
        elif mode == "pinned_codexpetdb":
            source = fixed_archive_url(petdb[kind])
        elif mode == "artist_nano":
            source = ("https://github.com/" + nano["repository"]
                      + "/tree/" + nano["revision"] + "/" + nano["asset_root"]
                      + "/" + nano["roles"][kind]["upstream_dir"] + "/img")
        else:
            row = external["sources"][kind]
            source = ("https://github.com/" + row["repository"]
                      + "/tree/" + row["revision"] + "/" + row["directory"])
        if not self.__showMessageBox(
                "本机安装公开作者动画",
                f"来源：{source}\n"
                "确认后下载固定版本原始动画，并安装为独立角色。"
                "不会覆盖现有桌宠或用户存档。"
                "公开素材与人物形象的人工验收是两回事；安装后请先预览。继续吗？"):
            return
        self.addButton.setEnabled(False)
        self.artistSourceButton.setEnabled(False)
        self.chibiThread = ChibiImportThread(
            kind, os.path.join(basedir, "res", "role"),
            mode=mode, profile=None, preset=kind, folder=None)
        self.chibiThread.done.connect(self._onChibiImportComplete)
        self.chibiThread.finished.connect(self._onChibiThreadFinished)
        self.chibiThread.start()
        self.__showSystemNote("正在下载并校验真实作者动画，安装后即可切换。", 1)

    def _showQuickStartGuide(self):
        from DyberPet.assistant.first_run_dialog import FirstRunRoleDialog
        dialog = FirstRunRoleDialog(
            Path(basedir) / "res" / "role",
            current_role=settings.petname, parent=self)
        if dialog.exec() and dialog.selected_role:
            self.__onLaunchClicked(dialog.selected_role)

    def _showAllCharacterCatalog(self):
        """Search all families using the same local evidence and preview engine."""
        from tools.character_progress import character_progress
        from .character_catalog_dialog import CharacterCatalogDialog
        from tools.genshin_library import scan_genshin_library
        try:
            progress=character_progress(Path(basedir)/"res"/"role")
        except (ValueError,OSError) as exc:
            self.__showSystemNote(self.tr("无法读取全部角色：")+str(exc),2)
            return
        dialog=CharacterCatalogDialog(progress,parent=self)
        if not dialog.exec():
            return
        selected=dialog.selection
        if selected=="__install_artist__":
            highlighted = dialog.selected_character_id()
            self._installArtistGenshin(
                highlighted if highlighted and highlighted.startswith("genshin_")
                else None)
            return
        if selected=="__manage_genshin__":
            self._showGenshinLibrary()
            return
        if selected in ("mascot_guga","mascot_doro"):
            self._showMascotLibrary(selected.split("_",1)[1])
            return
        if selected is None or not selected.startswith("genshin_"):
            return
        try:
            report=scan_genshin_library(Path(basedir)/"res"/"role")
        except (ValueError,OSError) as exc:
            self.__showSystemNote(self.tr("无法读取原神人物素材：")+str(exc),2)
            return
        role=next((x for x in report["characters"] if x["profile"]==selected),None)
        if role is None:
            self.__showSystemNote(self.tr("角色模板不再存在，请重新打开目录。"),2)
            return
        if not role["installed_folders"]:
            self.__showMessageBox(
                role["name"]+self.tr(" · 暂无动画"),
                self.tr("这个角色只有模板，没有通过本地结构检查的动画。"
                        "可从「添加角色」导入你已有权使用的素材。"))
            return
        self._openGenshinRoleActions(role)

    def _showGenshinLibrary(self):
        """Read-only overview; never call seed(), download art or install."""
        from tools.genshin_library import scan_genshin_library
        from tools.chibi_profiles import match_chibi_profile
        try:
            report = scan_genshin_library(Path(basedir) / "res" / "role")
        except (ValueError, OSError) as exc:
            self.__showSystemNote(self.tr("角色库读取失败：") + str(exc), 2)
            return
        summary = report["summary"]
        progress_label = "【进度】125 个角色的能力与素材覆盖情况"
        manage_label = "【管理】关联一个已安装但未归类的本地角色"
        unlink_label = "【管理】解除旧关联（不删除角色及动作）"
        labels = {}
        for role in report["characters"]:
            status = ("用户素材已安装 · 待实机验收"
                      if role["status"] == "structurally_installed" else
                      "原创演示动画可用 · 非官方角色美术"
                      if role["status"] == "demo_installed" else
                      "模板 · 待导入素材")
            name = f"{role['name']} · {status} [{role['profile']}]"
            labels[name] = role
        title = self.tr(
            f"原神角色库：{summary['template_count']} 个模板 / "
            f"{summary['installed_profile_count']} 个有动画（其中 "
            f"{summary['original_demo_profile_count']} 个程序原创演示）")
        chosen, accepted = QInputDialog.getItem(
            self, title,
            self.tr("选择角色查看状态；也可输入中文名、英文名或模板 ID。"
                    "本机扫描不访问网络，不认证角色来源。"),
            [progress_label, manage_label, unlink_label] + list(labels), 0, True)
        if not accepted:
            return
        if chosen == progress_label:
            self._showCharacterProgress(genshin_snapshot=report)
            return
        if chosen == manage_label:
            self._associateExistingGenshinRole(report)
            return
        if chosen == unlink_label:
            self._unlinkExistingGenshinRole()
            return
        role = labels.get(chosen)
        if role is None:
            try:
                selected = match_chibi_profile(chosen)
            except ValueError as exc:
                self.__showSystemNote(str(exc), 2)
                return
            role = next((x for x in report["characters"]
                         if x["profile"] == selected), None)
            if role is None:
                self.__showSystemNote("只显示原神人物模板。", 2)
                return
        if role["status"] not in ("structurally_installed", "demo_installed"):
            self.__showMessageBox(
                role["name"] + self.tr(" · 待导入素材"),
                self.tr("仅存在人物配置与动作建议。本机尚无与该模板绑定、"
                        "通过结构检查的本地角色素材。"
                        "请使用「添加角色」自行选择已取得的 ZIP 或动画文件夹。"))
            return
        self._openGenshinRoleActions(role)

    def _showCharacterProgress(self, genshin_snapshot=None):
        """Present actual *local* capability counts, never invent art or QA."""
        from tools.character_progress import character_progress
        try:
            data = character_progress(Path(basedir) / "res" / "role",
                                      genshin_snapshot=genshin_snapshot)
        except (ValueError, OSError) as exc:
            self.__showSystemNote(self.tr("角色进度检查失败：") + str(exc), 2)
            return
        s = data["summary"]
        rows = [
            f"模板数量：原神 {s['genshin_templates']} / 咕嘎、Doro {s['mascot_templates']}",
            f"原创可动演示：{s['original_demo_ready']} / {s['template_total']}",
            f"可在本机预览动作：{s['native_preview_ready']} / {s['template_total']}",
            f"另有个人导入美术：{s['personal_art_structurally_installed']} 人物",
            f"暂无本机可用动画：{s['missing_native_animation']} 人物",
            f"原神演示动作数：{s['genshin_demo_actions'] or '尚无'}",
            f"咕嘎 / Doro 演示动作数：{s['mascot_demo_actions'] or '尚无'}",
            "",
            "以上是本机 PNG/配置的结构验证，并非原作形象或声音还原验收。",
            "原设美术对照、人物原声、真实音频和长期桌面运行均需另行验收。",
            "角色库只读取本机文件，不会偷偷下载或修改素材。",
        ]
        self.__showMessageBox(self.tr("DyberPet · 角色实际完成度"),
                              "\n".join(rows))

    def _openGenshinRoleActions(self, role):
        """Preview, switch or inspect *any* safely recognized Genshin role.

        This is the same native animation dialog/controller used for Guga/Doro,
        not a second graphics engine or a claim of canonical game artwork.
        """
        folders = role["installed_folders"]
        if not folders:
            return
        # Personal art is offered before generated demonstration assets.
        choices = sorted(folders, key=lambda x: (bool(x["is_original_demo"]),
                                                  x["folder"].casefold()))
        options = {
            (f"{item['folder']} · {item['actions']} 类动作 / "
             f"{item['frames']} 帧 · " +
             ("程序原创 Q 版演示，非官方美术" if item["is_original_demo"]
              else "本机导入素材，原设与版权待核实")): item
            for item in choices
        }
        if len(choices) == 1:
            picked = choices[0]
        else:
            choice, accepted = QInputDialog.getItem(
                self, role["name"] + self.tr(" · 选择本机角色"),
                self.tr("本机真实导入的美术排列在演示皮肤之前："),
                list(options), 0, False)
            if not accepted or choice not in options:
                return
            picked = options[choice]
        name = picked["folder"]
        folder = Path(basedir) / "res" / "role" / name
        if not folder.is_dir() or folder.is_symlink():
            self.__showSystemNote(self.tr("角色文件夹丢失或无法安全读取。"), 2)
            return
        operations = [
            "▶ 预览真实动画动作（播放 / 暂停）",
            "✓ 切换成当前桌宠",
            "↗ 查看本机素材目录",
        ]
        action, accepted = QInputDialog.getItem(
            self, role["name"] + self.tr(" · 角色操作"),
            self.tr("原创演示不代表游戏角色的原设美术、模型或原声："),
            operations, 0, False)
        if not accepted:
            return
        if action == operations[0]:
            from .mascot_preview_dialog import MascotActionPreview
            try:
                viewer = MascotActionPreview(
                    folder, original_demo=bool(picked["is_original_demo"]),
                    parent=self)
            except (ValueError, OSError, TypeError) as exc:
                self.__showSystemNote(self.tr("预览无法打开：") + str(exc), 2)
                return
            viewer.exec()
        elif action == operations[1]:
            if name not in settings.pets:
                self.__showSystemNote(
                    self.tr("本机文件有效，但该角色尚未加载到当前桌宠会话。"
                            "重启 DyberPet 后再切换即可。"), 2)
                return
            self.__onLaunchClicked(name)
        elif action == operations[2]:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder.resolve())))

    def _associateExistingGenshinRole(self, report):
        """User-confirmed sidecar mapping of a previously installed local MOD."""
        candidates = [item for item in report["unmapped_local"]
                      if item["status"] == "unmapped_local"]
        if not candidates:
            self.__showMessageBox(
                self.tr("暂无可关联角色"),
                self.tr("只有已安装、结构有效且尚无角色身份记录的本地 MOD 才能关联。"
                        "如果原有关联失效，请先在本地校验或撤销过期记录。"))
            return
        choices = {
            f"{item['folder']} · {item['actions']} 类动作": item["folder"]
            for item in candidates
        }
        selected, accepted = QInputDialog.getItem(
            self, self.tr("关联已有角色（不重新导入）"),
            self.tr("选择本机已安装的单个角色文件夹："),
            list(choices), 0, False)
        if not accepted:
            return
        folder = choices.get(selected)
        if folder is None:
            return
        accepted, profile = self._chooseChibiProfile()
        if not accepted or not profile:
            return
        if not profile.startswith("genshin_"):
            self.__showSystemNote(self.tr("此入口只关联原神人物模板。"), 2)
            return
        from tools.chibi_profiles import CHIBI_PROFILES
        name = CHIBI_PROFILES[profile]["name"]
        if not self.__showMessageBox(
                self.tr("确认本地人物关联"),
                self.tr(f"把现有本地角色「{folder}」归入「{name}」？"
                        "只在 data 中保存人物与配置摘要，不修改、复制、"
                        "删除现有素材，不保证作品身份、许可或可玩效果。")):
            return
        try:
            from tools.genshin_role_bindings import associate_existing_role
            associate_existing_role(
                Path(basedir) / "res" / "role", folder, profile,
                mappings=Path(basedir) / "data" / "genshin_role_bindings.json",
                confirmed=True)
        except (ValueError, OSError) as exc:
            self.__showSystemNote(self.tr("本地关联失败：") + str(exc), 2)
            return
        self.__showSystemNote(
            self.tr(f"已将「{folder}」仅在本机归入「{name}」。"
                    "重新打开原神角色库即可查看；原始素材未改变。"), 1)

    def _unlinkExistingGenshinRole(self):
        """Undo mistaken/stale local mapping without touching source artwork."""
        root = Path(basedir) / "res" / "role"
        mappings = Path(basedir) / "data" / "genshin_role_bindings.json"
        try:
            from tools.genshin_role_bindings import (load_bindings,
                                                    unbind_existing_role)
            records = load_bindings(root, mappings)
        except (ValueError, OSError) as exc:
            self.__showSystemNote(self.tr("无法读取本地关联：") + str(exc), 2)
            return
        if not records:
            self.__showMessageBox(
                self.tr("暂无关联记录"),
                self.tr("这里只有手动建立的额外角色关联。"
                        "从文件导入时已带有人物身份的来源收据不会在此删除。"))
            return
        from tools.chibi_profiles import CHIBI_PROFILES
        options = {
            f"{folder} → {CHIBI_PROFILES[info['profile']]['name']}": folder
            for folder, info in sorted(records.items())
        }
        selected, accepted = QInputDialog.getItem(
            self, self.tr("解除本地关联"),
            self.tr("请选择要取消的额外人物映射；不会删除角色目录："),
            list(options), 0, False)
        if not accepted or selected not in options:
            return
        folder = options[selected]
        if not self.__showMessageBox(
                self.tr("确认解除关联"),
                self.tr(f"仅删除「{folder}」的本地人物映射记录？"
                        "原始动画、配置、声音和角色目录将保留不变。")):
            return
        try:
            unbind_existing_role(root, folder, mappings=mappings, confirmed=True)
        except (ValueError, OSError) as exc:
            self.__showSystemNote(self.tr("解除关联失败：") + str(exc), 2)
            return
        self.__showSystemNote(
            self.tr(f"已解除「{folder}」的本地人物关联，素材及动作未删除。"), 1)

    def _chooseChibiProfile(self):
        """Small modal selector, without adding permanent page controls."""
        from tools.chibi_profiles import CHIBI_PROFILES

        default_choice = "保留素材名称（Q版自动缩放）"
        # Name-first labels make Qt's editable combo completer useful with
        # dozens of role templates. Typing is navigation, not a new ID.
        options = {
            f"{data['name']} · {data['franchise']} [{key}]": key
            for key, data in CHIBI_PROFILES.items()
        }
        choices = [default_choice] + list(options)
        selected, accepted = QInputDialog.getItem(
            self, self.tr("Q版角色模板"),
            self.tr("可直接输入中文名/英文名；原生角色仅记录本机显示关联，需自行核对真实美术身份："),
            choices, 0, True
        )
        if not accepted:
            return False, None
        if selected == default_choice:
            return True, None
        if selected in options:
            return True, options[selected]
        # Editable Qt input is a practical search field with 122 presets.
        # Resolve exact Chinese/English names or an unambiguous prefix.
        from tools.chibi_profiles import match_chibi_profile
        try:
            return True, match_chibi_profile(selected)
        except ValueError as exc:
            self.__showSystemNote(self.tr(str(exc)), 2)
            return False, None

    def _importOriginalDemo(self):
        """Provide a real animated starter role for users with no art assets."""
        if self.chibiThread is not None:
            return
        if not self.__showMessageBox(
                self.tr("生成原创 Q 版桌宠"),
                self.tr("在本地生成原创星芽角色：待机、行走、挥手、跳跃、休息和阅读动作。"
                        "所有动画由程序绘制，不下载第三方美术或原声。"
                        "创建后可查看动作预览；仍须自行检查真实桌面效果。")):
            return
        self.addButton.setEnabled(False)
        self.chibiThread = ChibiImportThread(
            "", os.path.join(basedir, "res", "role"),
            mode="original_demo", profile=None, preset=None, folder=None)
        self.chibiThread.done.connect(self._onChibiImportComplete)
        self.chibiThread.finished.connect(self._onChibiThreadFinished)
        self.chibiThread.start()
        self.__showSystemNote(self.tr("正在生成原创 Q 版星芽动画，不会覆盖已有角色。"), 1)

    def _importPinnedPetDb(self, *, local_archive=False):
        """User-selected remote or previously downloaded SHA-pinned creator ZIP."""
        if self.chibiThread is not None:
            return
        from tools.install_pinned_codexpetdb import listed_packages
        from tools.chibi_profiles import CHIBI_PROFILES
        options = {
            CHIBI_PROFILES[item["profile"]]["name"] + " [" + item["slug"] + "]": key
            for key, item in sorted(listed_packages()["sources"].items())
        }
        selected, accepted = QInputDialog.getItem(
            self, self.tr("选择需要安装的原画角色"),
            self.tr("仅显示具有公开下载地址及固定 ZIP SHA-256 的四位人物："),
            list(options), 0, False)
        if not accepted or selected not in options:
            return
        archive_path = None
        if local_archive:
            archive_path, _ = QFileDialog.getOpenFileName(
                self, self.tr("选择已下载的原画 ZIP（须匹配固定 SHA-256）"),
                QStandardPaths.writableLocation(QStandardPaths.DocumentsLocation),
                "ZIP Archive (*.zip)")
            if not archive_path:
                return
        confirmation = QMessageBox.question(
            self, self.tr("个人本地导入确认" if local_archive else "个人本地下载确认"),
            self.tr("将校验本人已下载的原画 ZIP，文件长度与 SHA-256 必须完全匹配；" if local_archive
                    else "将从 CodexPetDB 下载第三方原画 ZIP，先验证完整 SHA-256，")
            + self.tr("然后仅解压宠物元数据与 PNG/WebP 图集。"
                    "来源原设形象尚未人工验收；不执行 ZIP 内脚本，也不覆盖已有角色。继续吗？"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        if confirmation != QMessageBox.StandardButton.Yes:
            return
        self.addButton.setEnabled(False)
        self.chibiThread = ChibiImportThread(
            archive_path if local_archive else options[selected],
            os.path.join(basedir, "res", "role"),
            mode="pinned_codexpetdb_local" if local_archive else "pinned_codexpetdb",
            profile=None, preset=options[selected], folder=None)
        self.chibiThread.done.connect(self._onChibiImportComplete)
        self.chibiThread.finished.connect(self._onChibiThreadFinished)
        self.chibiThread.start()
        self.__showSystemNote(
            self.tr("正在校验已下载的原画 ZIP；只有匹配 SHA-256 后才会安装。"
                    if local_archive else
                    "正在下载并核验固定 SHA-256 原画包；安装成功前不会更改现有角色。"), 1)

    def _importReactShimeji(self, modulePath):
        """Require an explicit one of six exact pinned identities."""
        if self.chibiThread is not None:
            return
        from tools.react_shimeji_source_leads import CANDIDATES
        from tools.chibi_profiles import CHIBI_PROFILES
        mapping = {
            CHIBI_PROFILES[profile]["name"] + " [" + profile + "]": profile
            for profile in sorted(CANDIDATES)
        }
        selected, accepted = QInputDialog.getItem(
            self, self.tr("选择对应原神人物"),
            self.tr("仅支持六位已固定 LFS SHA-256 的候选来源；仍需人工核对人物画风："),
            list(mapping), 0, False)
        if not accepted or selected not in mapping:
            return
        self.addButton.setEnabled(False)
        self.chibiThread = ChibiImportThread(
            modulePath, os.path.join(basedir, "res", "role"),
            mode="react_shimeji_lfs", profile=mapping[selected],
            preset=None, folder=None)
        self.chibiThread.done.connect(self._onChibiImportComplete)
        self.chibiThread.finished.connect(self._onChibiThreadFinished)
        self.chibiThread.start()
        self.__showSystemNote(
            self.tr("正在校验真实 LFS 模块 SHA-256 并从 PNG 图集读取原始帧；不执行 TypeScript。"), 1)

    def _importCodexZip(self, archivePath):
        """Convert a community Codex ZIP without unpacking executable payloads."""
        if self.chibiThread is not None:
            return
        accepted, profile = self._chooseChibiProfile()
        if not accepted:
            return
        if profile is None or not profile.startswith("genshin_"):
            self.__showSystemNote(
                self.tr("Codex ZIP 必须明确选择目标原神人物，不能凭文件名自动猜测。"), 2)
            return
        self.addButton.setEnabled(False)
        self.chibiThread = ChibiImportThread(
            archivePath, os.path.join(basedir, "res", "role"),
            mode="codex_zip", profile=profile, preset=None, folder=None)
        self.chibiThread.done.connect(self._onChibiImportComplete)
        self.chibiThread.finished.connect(self._onChibiThreadFinished)
        self.chibiThread.start()
        self.__showSystemNote(
            self.tr("正在校验并导入 Codex 原始精灵图集（不执行压缩包内程序）。"), 1)

    def _importShimejiZip(self, archivePath):
        """Import personal original Shimeji PNGs without launching archive programs."""
        if self.chibiThread is not None:
            return
        accepted, profile = self._chooseChibiProfile()
        if not accepted:
            return
        if profile is None or not profile.startswith("genshin_"):
            self.__showSystemNote(
                self.tr("Shimeji 原画需要明确选择对应的原神角色，不能自动猜测人物身份。"), 2)
            return
        self.addButton.setEnabled(False)
        self.chibiThread = ChibiImportThread(
            archivePath, os.path.join(basedir, "res", "role"),
            mode="shimeji_zip", profile=profile, preset=None, folder=None)
        self.chibiThread.done.connect(self._onChibiImportComplete)
        self.chibiThread.finished.connect(self._onChibiThreadFinished)
        self.chibiThread.start()
        self.__showSystemNote(
            self.tr("正在安全读取 Shimeji PNG 帧，不执行 ZIP 内任何程序。"), 1)

    def _importNativeZip(self, archivePath):
        """Import native ZIP with optional, explicit *local* profile association."""
        if self.chibiThread is not None:
            return
        accepted, profile = self._chooseChibiProfile()
        if not accepted:
            return
        self.addButton.setEnabled(False)
        self.chibiThread = ChibiImportThread(
            archivePath, os.path.join(basedir, "res", "role"),
            mode="native_zip", profile=profile, preset=None, folder=None
        )
        self.chibiThread.done.connect(self._onChibiImportComplete)
        self.chibiThread.finished.connect(self._onChibiThreadFinished)
        self.chibiThread.start()
        self.__showSystemNote(self.tr("正在验证并安装原生角色 ZIP。"), 1)

    def _importNativeFolder(self, sourceFolder):
        """Stage native MOD and optionally associate with selected chibi profile."""
        if self.chibiThread is not None:
            return
        accepted, profile = self._chooseChibiProfile()
        if not accepted:
            return
        self.addButton.setEnabled(False)
        self.chibiThread = ChibiImportThread(
            sourceFolder, os.path.join(basedir, "res", "role"),
            mode="native_folder", profile=profile, preset=None, folder=None)
        self.chibiThread.done.connect(self._onChibiImportComplete)
        self.chibiThread.finished.connect(self._onChibiThreadFinished)
        self.chibiThread.start()
        self.__showSystemNote(self.tr(
            "正在安全检查并导入原生角色文件夹（不会覆盖已有角色）。"), 1)

    def _importCodexCharacter(self, sourceFolder):
        self._importLocalChibi(sourceFolder, mode="codex")

    def _importLocalChibi(self, sourceFolder, mode):
        """Convert user artwork on a worker; keep the Qt main thread responsive."""
        if self.chibiThread is not None:
            return
        from tools.chibi_profiles import available_role_folder
        accepted, profile = self._chooseChibiProfile()
        if not accepted:
            return
        # Use a distinct ASCII folder for each named template. The previewed
        # artwork remains entirely user-supplied, not bundled or downloaded.
        folder_name = "".join(word.capitalize() for word in profile.split("_")) if profile else None
        preset = None
        if mode == "codex" and profile is None:
            try:
                manifest = json.loads(
                    (Path(sourceFolder) / "pet.json").read_text(encoding="utf-8"))
                preset = {"guga--circus": "guga",
                          "doro--lingxiaotian": "doro"}.get(manifest.get("id"))
            except (ValueError, OSError) as exc:
                self.__showSystemNote("Invalid Codex pet.json: " + str(exc), 2)
                return

        # The exact source name may be Chinese or collide with an installed
        # role; allocate a new safe folder instead of overwriting existing art.
        if folder_name is None:
            folder_name = (preset.title() if preset else Path(sourceFolder).name)
        folder_name = available_role_folder(
            Path(basedir) / "res" / "role", folder_name
        )
        self.addButton.setEnabled(False)
        self.chibiThread = ChibiImportThread(
            sourceFolder, os.path.join(basedir, "res", "role"),
            mode=mode, profile=profile, preset=preset, folder=folder_name
        )
        self.chibiThread.done.connect(self._onChibiImportComplete)
        self.chibiThread.finished.connect(self._onChibiThreadFinished)
        self.chibiThread.start()
        self.__showSystemNote(self.tr("正在转换Q版角色，导入期间可继续查看其他页面。"), 1)

    def _onChibiImportComplete(self, role_name, error):
        if error:
            if (self.chibiThread is not None and
                    self.chibiThread.mode in ("pinned_codexpetdb", "pinned_codexpetdb_local")):
                if ("429" in error or "Too Many Requests" in error):
                    error = (
                        "原画来源站点暂时限制下载请求（HTTP 429）。"
                        "您可以从作者页面下载对应 ZIP 后，使用「添加角色 → "
                        "已下载的 SHA-256 固定原画 ZIP（断网可用）」导入。"
                        "只有固定哈希完全匹配的原件才会被安装，已有角色不受影响。"
                    )
                elif ("SHA-256" in error or "length differs" in error or
                      "pet.json.id" in error):
                    error = (
                        "原画安装被安全校验拒绝：" + error[:260] +
                        "。请检查所选人物和 ZIP 是否与固定发布版本完全一致。"
                        "不要关闭校验或用其他人物的素材替代。"
                    )
            if (self.chibiThread is not None and
                    self.chibiThread.mode == "creator_source"):
                error = (self.tr("未能安装作者动画素材：") + error[:360] +
                         self.tr("\n内置原创咕嘎 / Doro 演示版仍可正常使用。"
                                 "请检查网络后再次点击「联网安装」；"
                                 "安全校验不通过时不要尝试绕过 SHA-256。"
                                 "原有角色文件未被覆盖。"))
            self.__showMessageBox(self.tr("Adding Failed"), error)
            return
        self.newPetFolder = role_name
        self.__onAddClickedContinue()
        preview = Path(basedir) / "res" / "role" / role_name / "ANIMATION_PREVIEW.png"
        source_mode = self.chibiThread.mode if self.chibiThread is not None else ""
        title = ("作者真实动作帧核对（非人工验收通过）"
                 if source_mode in ("artist_genshin", "artist_codex", "artist_shimeji", "artist_nano", "artist_external_codex", "pinned_codexpetdb", "pinned_codexpetdb_local", "react_shimeji_lfs", "creator_source")
                 else "角色动作帧预览")
        message = ("安装成功。是否打开由原作者 PNG 原始帧直接拼成的核对图？"
                   "请检查脸部、发饰、服装和动作是否确实属于所选角色。"
                   "预览不等于自动完成形象验收。"
                   if source_mode in ("artist_genshin", "artist_codex", "artist_shimeji", "artist_nano", "artist_external_codex", "pinned_codexpetdb", "pinned_codexpetdb_local", "react_shimeji_lfs", "creator_source")
                   else "角色已导入。是否打开动作帧预览图，检查动画素材？")
        if preview.is_file() and self.__showMessageBox(title, message):
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(preview.resolve())))

    def _onChibiThreadFinished(self):
        self.addButton.setEnabled(True)
        self.artistSourceButton.setEnabled(True)
        thread = self.chibiThread
        self.chibiThread = None
        if thread is not None:
            thread.deleteLater()

    def _importChar(self, sourceFolder, destinationFolder):

        # Copy folders
        self.thread = FileCopyThread(sourceFolder, destinationFolder)
        self.thread.started.connect(self._startStateTooltip)
        self.thread.done.connect(self._stopStateTooltip)
        self.thread.start()

        # stop processing note
        #self._stopStateTooltip(True)
        #return 1

    def __onAddClickedContinue(self):

        # Add pet in settings.pet
        petFolder = self.newPetFolder
        settings.pets.append(petFolder)
        settings.defaultAct[petFolder] = None

        # Add pet in basicSetting change pet tab - not implemented yet

        # Add character List and Card
        iCard = len(self.CharLineList)
        infoLine = CharLine(iCard, chrFolder=petFolder, parent=self.CharCardGroup)
        self.CharCardGroup.addInfoCard(infoLine)
        self.CharLineList.append(infoLine)
        
        infoFile = os.path.join(basedir,"res/role", petFolder, "info/info.json")
        if not os.path.exists(infoFile):
            self.CharCardList.append(None)
        else:
            card = CharCard(iCard, jsonPath=infoFile, petFolder=petFolder)
            self.CharCardList.append(card)

        self.CharLineList[iCard].launchClicked.connect(self.__onLaunchClicked)
        if os.path.exists(infoFile):
            self.CharLineList[iCard].infoClicked.connect(self.__onInfoClicked)
    
            self.CharCardList[iCard].card.gotoClicked.connect(self.__onGotoClicked)
            self.CharCardList[iCard].card.deleteClicked.connect(self.__onDeleteClicked)

        self._applyDemoRoleVisibility()
        content = self.tr("Adding character completed! It's recommended to restart the App to have all features enabled.")
        self.__showSystemNote(content, 0)

        self.newPetFolder = None


    def _startStateTooltip(self):
        if self.stateTooltip:
            return
        self.stateTooltip = StateToolTip(
            self.tr('Copying Files'), self.tr('Please wait patiently'), self.window())
        self.stateTooltip.move(self.stateTooltip.getSuitablePos())
        self.stateTooltip.show()

    def _stopStateTooltip(self, success=True):
        if not self.stateTooltip:
            pass
        elif success:
            self.stateTooltip.setContent(
                self.tr('Copy complete!') + ' 😆')
            self.stateTooltip.setState(True)
            self.stateTooltip = None
            self.__onAddClickedContinue()
        else:
            self.stateTooltip.setState(True)
            self.stateTooltip = None
            content = self.tr("Copying folder failed with unknown reason.")
            self.__showSystemNote(content, 2)
            self.newPetFolder = None
        
        self._terminateThread()

    def _terminateThread(self):
        if self.thread:
            self.thread.quit()  # Terminate the thread
            self.thread.wait()  # Wait until it's fully terminated
            self.thread = None 


    def _send_CharImportResult(self, statCode, errorList):
        title = self.tr("Adding Failed")
        stat_notes = [self.tr("Success!"),
                      self.tr("pet_conf.json broken or not exist!"),
                      self.tr("act_conf.json broken or not exist"),
                      self.tr('The following actions are missing "images" attribute:'),
                      self.tr("The following image files missing:"),
                      self.tr("The following default actions missing in pet_conf.json:"),
                      self.tr("The following actions called by pet_conf.json are missing from act_conf.json:")]
        content = stat_notes[statCode]
        if errorList is not None:
            content += '\n' + ', '.join(errorList)

        self.__showMessageBox(title, content)
        return
    
    def _send_itemImportResult(self, statCode, errorList):
        title = self.tr("Adding Failed")
        stat_notes = [self.tr("Success!"),
                      self.tr("items_config.json broken or not exist."),
                      self.tr("'image' key missing:"),
                      self.tr('The following items are missing image files:'),
                      self.tr("In the following items, 'pet_limit' is not a list:")]
        content = stat_notes[statCode]
        if errorList is not None:
            content += '\n' + ', '.join(errorList)

        self.__showMessageBox(title, content)
        return

    def __onShowInstruction(self):
        title = self.tr("Character Management Guide")
        content_1 = self.tr("""This panel shows all the characters you have so far.
You can switch to a char, or check the character information.

By clicking Add Characters, you can import a new one from the selected folder.
To find new characters, you can check our official collection by clicking the hyperlink button.

For most of time, App can import the character for you automatically. But in any case you want to add it manually:""")
        content_2 = self.tr("1. Prepare the character folder containing all files;\n2. Copy the folder to App resource folder (you can click 'Go to Folder' button);\n3. Close App and open again;\n4. You will see the character show up here;\n5. Click 'Launch' to start;\n6. If App crushed, it means the character file is problematic, please contact the author for help.")
        content = f"{content_1}\n{content_2}"
        if not self.__showMessageBox(title, content, cancelText=self.tr("Go to Folder")):
            resFolder = os.path.join(basedir, 'res/role')

            if platform == 'win32':
                os.startfile(os.path.normpath(resFolder))
            elif platform == "darwin":
                subprocess.call(["open", os.path.normpath(resFolder)])
            else:
                # For Linux - not tested
                subprocess.call(["xdg-open", os.path.normpath(resFolder)])
        else:
            return
        

    def __showMessageBox(self, title, content, yesText='OK', cancelText=None):

        WarrningMessage = MessageBox(title, content, self)
        if yesText == 'OK':
            WarrningMessage.yesButton.setText(self.tr('OK'))
        else:
            WarrningMessage.yesButton.setText(yesText)
        if cancelText:
            WarrningMessage.cancelButton.setText(cancelText)
        else:
            WarrningMessage.cancelButton.setText(self.tr('Cancel'))

        if WarrningMessage.exec():
            return True
        else:
            #print('Cancel button is pressed')
            return False

    def __showSystemNote(self, content, type_code, duration=5000):
        """ show restart tooltip """
        notMethods = [InfoBar.success, InfoBar.warning, InfoBar.error]
        notMethods[type_code](
            '',
            content,
            duration=duration,
            position=InfoBarPosition.BOTTOM,
            parent=self.window()
        )





def get_child_folder(parentFolder, relative=False):
    all_files_and_dirs = os.listdir(parentFolder)
    if relative:
        all_dirs = [os.path.basename(d) for d in all_files_and_dirs if os.path.isdir(os.path.join(parentFolder, d))]
    else:
        all_dirs = [d for d in all_files_and_dirs if os.path.isdir(os.path.join(parentFolder, d))]

    return all_dirs


class FileCopyThread(QThread):
    started = Signal()
    done = Signal(bool)

    def __init__(self, source, destination):
        super(FileCopyThread, self).__init__()
        self.source = source
        self.destination = destination

    def run(self):
        # Assuming you want to copy a directory
        # You can change this to suit your needs
        self.started.emit()
        try:
            copytree(self.source, self.destination)
        except:
            self.done.emit(False)
            return

        # Emitting progress and done signals as an example
        self.done.emit(True)


class ChibiImportThread(QThread):
    """Converts local assets and runs DyberPet config preflight off the UI thread."""
    done = Signal(str, str)

    def __init__(self, source, output_root, *, mode, profile, preset, folder):
        super().__init__()
        self.source = Path(source)
        self.output_root = Path(output_root)
        self.mode = mode
        self.profile = profile
        self.preset = preset
        self.folder = folder

    def run(self):
        new_folder = None
        try:
            if self.mode == "original_demo":
                from tools.create_original_mascot import create_original_mascot
                new_folder = create_original_mascot(self.output_root)
            elif self.mode == "artist_genshin":
                from tools.install_artist_genshin import install_artist_genshin
                installed = install_artist_genshin(
                    self.preset, self.output_root, confirmed=True)
                new_folder = self.output_root / installed["folder"]
            elif self.mode == "artist_codex":
                from tools.install_artist_codex import install_artist_codex
                installed = install_artist_codex(
                    self.preset, self.output_root, confirmed=True)
                new_folder = self.output_root / installed["folder"]
            elif self.mode == "artist_shimeji":
                from tools.install_artist_shimeji import install_artist_shimeji
                installed = install_artist_shimeji(
                    self.preset, self.output_root, confirmed=True)
                new_folder = self.output_root / installed["folder"]
            elif self.mode == "artist_nano":
                from tools.install_nanopet_shimeji import install_nanopet_shimeji
                installed = install_nanopet_shimeji(
                    self.preset, self.output_root, confirmed=True)
                new_folder = self.output_root / installed["folder"]
            elif self.mode == "artist_external_codex":
                from tools.install_external_codex import install_external_codex
                installed = install_external_codex(
                    self.preset, self.output_root, confirmed=True)
                new_folder = self.output_root / installed["folder"]
            elif self.mode == "creator_source":
                from tools.install_creator_mascots import install_creator_mascot
                installed = install_creator_mascot(
                    self.preset, self.output_root, confirmed=True)
                new_folder = self.output_root / installed["folder"]
            elif self.mode in ("pinned_codexpetdb", "pinned_codexpetdb_local"):
                from tools.install_pinned_codexpetdb import install_pinned_codexpetdb
                # self.source is always Path: use selected string registry key,
                # not Path("kaveh") which fails membership checks in source index.
                source_key = self.preset if self.preset is not None else str(self.source)
                new_folder = install_pinned_codexpetdb(
                    source_key, self.output_root, confirmed=True,
                    archive=self.source if self.mode == "pinned_codexpetdb_local" else None)
            elif self.mode == "react_shimeji_lfs":
                from tools.install_pinned_react_shimeji import install_pinned_react_shimeji
                new_folder = install_pinned_react_shimeji(
                    self.source, self.output_root,
                    profile=self.profile, confirmed=True)
            elif self.mode == "codex_zip":
                from tools.install_personal_codex_zip import install_personal_codex_zip
                new_folder = install_personal_codex_zip(
                    self.source, self.output_root,
                    profile=self.profile, confirmed=True)
            elif self.mode == "shimeji_zip":
                from tools.install_personal_shimeji_zip import install_personal_shimeji_zip
                new_folder = install_personal_shimeji_zip(
                    self.source, self.output_root,
                    profile=self.profile, confirmed=True)
            elif self.mode in ("native_zip", "native_folder"):
                if self.profile:
                    # Attach only the user-selected display identity; never
                    # infer the character from art names or assert permissions.
                    from tools.personal_role_import import personal_install
                    new_folder = personal_install(
                        self.source, self.output_root,
                        profile=self.profile, confirm_local_only=True)
                elif self.mode == "native_zip":
                    from tools.install_native_role import install_native_role
                    new_folder = install_native_role(self.source, self.output_root)
                else:
                    from tools.install_native_role import install_native_folder
                    new_folder = install_native_folder(self.source, self.output_root)
            elif self.mode == "codex":
                from tools.import_codex_pet import convert
                new_folder = convert(
                    self.source, self.output_root, preset=self.preset,
                    profile=self.profile, style="chibi", folder=self.folder
                )
            else:
                from tools.import_chibi_animations import convert_animation_folder
                new_folder = convert_animation_folder(
                    self.source, self.output_root, profile=self.profile,
                    folder=self.folder,
                )
            status, problem = CheckCharFiles(str(new_folder))
            if status:
                # Never keep a role that may crash the game.
                rmtree(new_folder)
                new_folder = None
                raise ValueError(
                    f"Character validation failed (code {status}): {problem}"
                )
            self.done.emit(new_folder.name, "")
        except Exception as exc:
            # Clean up only the role directory created in this execution.
            # Existing roles cannot be overwritten by either importer.
            if new_folder is not None and new_folder.exists():
                rmtree(new_folder, ignore_errors=True)
            self.done.emit("", str(exc))
