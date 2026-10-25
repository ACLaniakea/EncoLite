"""Native Windows Installer wizard; no bootstrapper or bundled UI runtime."""
from pathlib import Path
import msilib as m
from msilib import sequence


def add_wizard(db,root:Path,exe:str,arguments:str):
    m.add_data(db,'TextStyle',[('UiNormal','Segoe UI',9,None,0),('UiTitle','Segoe UI',15,0x003B5930,1),('UiSmall','Segoe UI',8,None,0)])
    m.add_data(db,'Property',[('DefaultUIFont','UiNormal'),('ErrorDialog','ErrorDlg'),('LAUNCH_AFTER_INSTALL','1'),('MsiLogging','voicewarmupx')])
    m.add_data(db,'CheckBox',[('CREATE_DESKTOP_SHORTCUT','1'),('LAUNCH_AFTER_INSTALL','1')])
    m.add_data(db,'CustomAction',[('DefaultDesktopShortcut',51,'CREATE_DESKTOP_SHORTCUT','1')])
    rows=list(sequence.InstallUISequence)
    m.change_sequence(rows,'LaunchConditions',450)
    rows.extend([('UseExistingDirectory','EXISTINGINSTALLDIR',425),
                 ('SetInstallLocation',None,1010),
                 ('DefaultDesktopShortcut','NOT Installed AND NOT CREATE_DESKTOP_SHORTCUT',760),
                 ('WelcomeDlg','NOT Installed AND UILevel >= 4',1230),
                 ('MaintenanceDlg','Installed AND UILevel >= 4',1230),
                 ('ProgressDlg','UILevel >= 4',1280)])
    m.add_data(db,'InstallUISequence',rows)

    def page(name,title,first,default,cancel='Cancel',modeless=False):
        d=m.Dialog(db,name,50,50,430,300,1 if modeless else 3,'[ProductName] 安装程序',first,default,cancel)
        d.text('Heading',22,18,386,28,3,r'{\UiTitle}'+title)
        d.text('Version',22,50,386,17,3,'Enco Lite  [ProductRelease]')
        d.line('HeaderLine',0,76,430,0);d.line('FooterLine',0,260,430,0)
        return d
    def button(d,name,label,x,next_name,event=None,arg=None,condition='1'):
        b=d.pushbutton(name,x,273,62,18,3,label,next_name)
        if event:b.event(event,arg,condition,1)
        return b
    def cancel(d,next_name='Next'):return button(d,'Cancel','取消(&C)',349,next_name,'EndDialog','Exit')

    welcome=page('WelcomeDlg','欢迎安装 Enco Lite','Next','Next')
    welcome.text('Intro',22,96,386,54,3,'OPPO / 一加蓝牙耳机控制客户端。\r\n\r\n接下来可以选择安装位置并创建桌面快捷方式。')
    welcome.text('Tray',22,164,386,32,3,'安装后可从开始菜单或桌面打开程序。关闭主窗口后，耳机连接与托盘继续运行。')
    welcome.text('LicenseText',22,212,286,24,3,'开源软件 · GPL-3.0-or-later')
    welcome.pushbutton('License',326,215,82,18,3,'查看许可证','Next').event('SpawnDialog','LicenseDlg','1',1)
    button(welcome,'Next','下一步(&N)',278,'Cancel','NewDialog','OptionsDlg');cancel(welcome,'License')

    options=page('OptionsDlg','选择安装位置','Path','Next')
    options.text('PathLabel',22,88,386,16,3,'安装到：')
    path=options.control('Path','PathEdit',22,108,316,22,3,'INSTALLDIR',None,'Browse',None)
    browse=options.pushbutton('Browse',348,108,60,22,3,'浏览(&B)','Desktop')
    browse.event('[_BrowseProperty]','INSTALLDIR','1',1);browse.event('SpawnDialog','BrowseDlg','1',2)
    for control in (path,browse):control.condition('Disable','OLDPRODUCTS OR Installed')
    options.text('UpgradeHint',22,138,386,28,3,'升级现有安装时保留原来的安装位置。').condition('Hide','NOT OLDPRODUCTS')
    options.checkbox('Desktop',22,173,386,20,3,'CREATE_DESKTOP_SHORTCUT','创建桌面快捷方式(&D)','Back')
    options.text('Settings',22,209,386,30,3,'程序安装到当前用户目录。卸载时保留个人设置。')
    button(options,'Back','上一步(&B)',207,'Next','NewDialog','WelcomeDlg')
    nxt=button(options,'Next','下一步(&N)',278,'Cancel')
    nxt.event('SetTargetPath','INSTALLDIR','NOT OLDPRODUCTS AND NOT Installed',1)
    nxt.event('NewDialog','ReadyDlg','1',2);cancel(options,'Path')

    folder=page('BrowseDlg','选择文件夹','Folders','OK','Cancel')
    folder.control('Folders','DirectoryCombo',22,91,294,20,11,'_BrowseProperty',None,'Up',None)
    folder.pushbutton('Up',326,91,82,20,3,'上一级','List').event('DirectoryListUp','0','1',1)
    folder.control('List','DirectoryList',22,121,386,95,11,'_BrowseProperty',None,'Path',None)
    folder.control('Path','PathEdit',22,225,386,22,11,'_BrowseProperty',None,'OK',None)
    ok=button(folder,'OK','确定',278,'Cancel');ok.event('SetTargetPath','[_BrowseProperty]','1',1);ok.event('EndDialog','Return','1',2)
    button(folder,'Cancel','取消',349,'Folders','EndDialog','Return')

    ready=page('ReadyDlg','准备安装','Install','Install')
    ready.text('Intro',22,96,386,32,3,'点击“安装”开始复制程序文件并创建开始菜单入口。')
    ready.text('PathLabel',22,144,386,16,3,'安装位置：')
    ready.text('Target',22,164,386,52,131075,'[INSTALLDIR]')
    button(ready,'Back','上一步(&B)',207,'Install','NewDialog','OptionsDlg')
    button(ready,'Install','安装(&I)',278,'Cancel','EndDialog','Return');cancel(ready,'Back')

    maintenance=page('MaintenanceDlg','维护 Enco Lite','Repair','Repair')
    maintenance.text('Intro',22,94,386,34,3,'当前版本已经安装。你可以修复程序文件，或移除此应用。')
    maintenance.text('Target',22,137,386,42,131075,'[INSTALLDIR]')
    maintenance.text('Settings',22,197,386,24,3,'修复和卸载都会保留个人设置。')
    repair=button(maintenance,'Repair','修复(&R)',207,'Remove');repair.event('[REMOVE]','{}','1',1);repair.event('[REINSTALL]','ALL','1',2);repair.event('[REINSTALLMODE]','amus','1',3);repair.event('EndDialog','Return','1',4)
    remove=button(maintenance,'Remove','卸载(&U)',278,'Cancel');remove.event('[REINSTALL]','{}','1',1);remove.event('[REMOVE]','ALL','1',2);remove.event('EndDialog','Return','1',3)
    button(maintenance,'Cancel','取消(&C)',349,'Repair','EndDialog','Exit')

    progress=page('ProgressDlg','正在处理安装','Cancel','Cancel',modeless=True)
    progress.text('Intro',22,99,386,30,3,'请稍候，正在更新程序文件与快捷方式。')
    action=progress.text('Action',22,145,386,20,3,'准备文件…');action.mapping('ActionText','Text')
    bar=progress.control('Progress','ProgressBar',22,177,386,14,1,None,None,None,None);bar.mapping('SetProgress','Progress')
    progress.text('Detail',22,202,386,34,131075,'').mapping('ActionData','Text')
    button(progress,'Cancel','取消(&C)',349,'Cancel','EndDialog','Exit')

    done=page('ExitDialog','操作已完成','Finish','Finish','Finish')
    done.text('Installed',22,99,386,40,3,'Enco Lite 已安装完成，可从开始菜单或桌面打开。').condition('Hide','REMOVE~="ALL"')
    done.text('Removed',22,99,386,40,3,'Enco Lite 已移除，个人设置仍然保留。').condition('Hide','NOT REMOVE~="ALL"')
    launch=done.checkbox('Launch',22,167,386,20,3,'LAUNCH_AFTER_INSTALL','打开 Enco Lite(&L)','Finish');launch.condition('Hide','REMOVE~="ALL"')
    finish=button(done,'Finish','完成(&F)',349,'Launch')
    finish.event('MsiLaunchApp','"[#'+exe+']" '+arguments+' --restart','LAUNCH_AFTER_INSTALL=1 AND NOT REMOVE~="ALL"',1)
    finish.event('EndDialog','Return','1',2)

    for name,title,body in [('FatalError','安装未完成','安装遇到错误，未能完成。请检查安装文件和目标目录后重试。\r\n安装日志：[MsiLogFileLocation]'),('UserExit','已取消安装','安装已取消。你可以稍后重新运行安装程序。')]:
        d=page(name,title,'Close','Close','Close');d.text('Body',22,100,386,110,131075,body)
        button(d,'Close','关闭',349,'Close','EndDialog','Return')

    license=m.Dialog(db,'LicenseDlg',50,50,430,300,3,'开源许可证','Close','Close','Close')
    text=(root/'LICENSE').read_text('utf-8').replace('\\',r'\\').replace('{',r'\{').replace('}',r'\}').replace('\n',r'\par ')
    license.control('Text','ScrollableText',12,12,406,243,3,None,r'{\rtf1\ansi\deff0{\fonttbl{\f0 Segoe UI;}}\f0\fs16 '+text+'}',None,None)
    button(license,'Close','关闭',349,'Close','EndDialog','Return')

    error=m.Dialog(db,'ErrorDlg',50,50,430,180,65539,'[ProductName]','ErrorText',None,None)
    error.text('ErrorText',22,20,386,105,3,'')
    for name,label in [('Ok','确定'),('Cancel','取消'),('Abort','终止'),('Retry','重试'),('Ignore','忽略'),('Yes','是'),('No','否')]:
        error.pushbutton(name,180,145,62,18,3,label,None).event('EndDialog','Error'+name,'1',1)
