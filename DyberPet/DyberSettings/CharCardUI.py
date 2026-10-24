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
from PySide6.QtWidgets import QWidget, QLabel, QApplication, QFileDialog, QInputDialog, QSizePolicy, QHBoxLayout, QSpacerItem

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

        # Button to show instructions on how to manually add chars
        #self.instructButton = TransparentPushButton(self.tr("Add Chars Manually"), self, FIF.QUESTION)
        #self.instructButton.setSizePolicy(QSizePolicy.Maximum, self.instructButton.sizePolicy().verticalPolicy())

        self.headerWidget = QWidget(self)
        self.headerWidget.setFixedWidth(sizeHintDyber[0]-165)
        self.headerLayout = QHBoxLayout(self.headerWidget)
        self.headerLayout.setContentsMargins(0, 0, 0, 0)
        self.headerLayout.setSpacing(0)

        self.headerLayout.addWidget(self.addButton, Qt.AlignLeft | Qt.AlignVCenter)
        spacerItem1 = QSpacerItem(15, 20, QSizePolicy.Fixed, QSizePolicy.Minimum)
        self.headerLayout.addItem(spacerItem1)
        self.headerLayout.addWidget(self.CharListLink, Qt.AlignLeft | Qt.AlignVCenter)
        #spacerItem2 = QSpacerItem(15, 20, QSizePolicy.Fixed, QSizePolicy.Minimum)
        #self.headerLayout.addItem(spacerItem2)
        #self.headerLayout.addWidget(self.instructButton, Qt.AlignLeft | Qt.AlignVCenter)
        spacerItem3 = QSpacerItem(15, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.headerLayout.addItem(spacerItem3)
        

        self.__initCardLayout()

        self.__initWidget()

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
        self.panelHelp.clicked.connect(self.__onShowInstruction)

    def __onLaunchClicked(self, petname):
        # Ignore if it's current char
        if settings.petname == petname:
            return
        # Confirm
        title = self.tr('Switch to ') + petname + "?"
        content = self.tr("Might take some time, just wait a moment <3")
        if not self.__showMessageBox(title, content):
            return

        self._launchStateTooltip()
        self.change_pet.emit(petname)

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
        options = ["个人本地导入：角色文件夹 / Codex / GIF / PNG", "个人本地导入：原生角色 ZIP",
                   "生成原创 Q 版示例角色（不需下载素材）"]
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
            self.tr("可输入角色名首字快速查找；必须选列表中已有模板："),
            choices, 0, True
        )
        if not accepted:
            return False, None
        if selected == default_choice:
            return True, None
        if selected not in options:
            self.__showSystemNote(self.tr("请选择下拉列表中的角色模板。"), 2)
            return False, None
        return True, options[selected]

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

    def _importNativeZip(self, archivePath):
        """Install existing native role ZIP without changing existing roles."""
        if self.chibiThread is not None:
            return
        self.addButton.setEnabled(False)
        self.chibiThread = ChibiImportThread(
            archivePath, os.path.join(basedir, "res", "role"),
            mode="native_zip", profile=None, preset=None, folder=None
        )
        self.chibiThread.done.connect(self._onChibiImportComplete)
        self.chibiThread.finished.connect(self._onChibiThreadFinished)
        self.chibiThread.start()
        self.__showSystemNote(self.tr("正在验证并安装原生角色 ZIP。"), 1)

    def _importNativeFolder(self, sourceFolder):
        """Safely stage an extracted single main-role MOD on a worker thread."""
        if self.chibiThread is not None:
            return
        self.addButton.setEnabled(False)
        self.chibiThread = ChibiImportThread(
            sourceFolder, os.path.join(basedir, "res", "role"),
            mode="native_folder", profile=None, preset=None, folder=None)
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
            self.__showMessageBox(self.tr("Adding Failed"), error)
            return
        self.newPetFolder = role_name
        self.__onAddClickedContinue()
        preview = Path(basedir) / "res" / "role" / role_name / "ANIMATION_PREVIEW.png"
        if preview.is_file() and self.__showMessageBox(
                self.tr("Q版角色动作预览"),
                self.tr("角色已导入。是否打开生成的动作帧预览图，检查动画素材？")):
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(preview.resolve())))

    def _onChibiThreadFinished(self):
        self.addButton.setEnabled(True)
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
            elif self.mode == "native_zip":
                from tools.install_native_role import install_native_role
                new_folder = install_native_role(self.source, self.output_root)
            elif self.mode == "native_folder":
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
