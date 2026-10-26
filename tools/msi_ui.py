"""Native MSI wizard with conventional Windows Installer pages and controls."""
from pathlib import Path
import msilib as m
from msilib import sequence


def add_wizard(db, root: Path, entry_point: str, arguments: str):
    m.add_data(db, 'TextStyle', [
        ('UiNormal', 'Microsoft YaHei UI', 9, None, 0),
        ('UiTitle', 'Microsoft YaHei UI', 12, None, 1),
    ])
    m.add_data(db, 'Binary', [('InstallerIcon', m.Binary(str(root/'build/installer-assets/icon.bmp'))),
                               ('InstallerHeader', m.Binary(str(root/'build/installer-assets/header.bmp')))])
    m.add_data(db, 'Property', [
        ('DefaultUIFont', 'UiNormal'), ('ErrorDialog', 'ErrorDlg'),
        ('LAUNCH_AFTER_INSTALL', '1'), ('MsiLogging', 'voicewarmupx'),
        ('WizardProgressTitle', '正在安装'), ('WizardFinishTitle', '安装完成'),
        ('WizardWindowTitle', 'Enco Lite 安装程序'),
        ('RMCHOICE', 'Close'),
    ])
    m.add_data(db, 'CheckBox', [('CREATE_DESKTOP_SHORTCUT', '1'), ('LAUNCH_AFTER_INSTALL', '1')])
    m.add_data(db,'ActionText',[(name,text,'') for name,text in {
        'CostInitialize':'正在计算所需空间…','FileCost':'正在检查程序文件…','CostFinalize':'正在检查安装位置…',
        'InstallValidate':'正在检查安装状态…','ProcessComponents':'正在处理程序组件…',
        'InstallFiles':'正在复制程序文件…','RemoveFiles':'正在移除程序文件…',
        'WriteRegistryValues':'正在保存程序信息…','RemoveRegistryValues':'正在移除程序信息…',
        'CreateShortcuts':'正在创建快捷方式…','RemoveShortcuts':'正在移除快捷方式…',
        'RegisterProduct':'正在注册 Enco Lite…','PublishProduct':'正在完成安装…',
        'UnpublishFeatures':'正在移除组件信息…','RegisterUser':'正在保存安装信息…',
        'RemoveExistingProducts':'正在移除旧版本…','InstallFinalize':'正在完成操作…',
        'RemoveAutostart':'正在移除开机自启动项…',
    }.items()])
    m.add_data(db, 'CustomAction', [
        ('DefaultDesktopShortcut', 51, 'CREATE_DESKTOP_SHORTCUT', '1'),
        ('RememberRemoveRequest', 51, 'RemoveRequested', '1'),
        ('SetLauncher', 51, 'INSTALLER_PYTHON', '[INSTALLDIR]'+entry_point.replace('/', '\\')),
        ('LaunchApplication', 242, 'INSTALLER_PYTHON', arguments+' --restart'),
    ])
    rows = list(sequence.InstallUISequence)
    m.change_sequence(rows, 'LaunchConditions', 450)
    rows.extend([
        ('UseExistingDirectory', 'EXISTINGINSTALLDIR', 425),
        ('SetInstallLocation', None, 1010),
        ('DefaultDesktopShortcut', 'NOT Installed AND NOT CREATE_DESKTOP_SHORTCUT', 760),
        ('RememberRemoveRequest', 'Installed AND REMOVE~="ALL"', 1100),
        ('WelcomeDlg', 'NOT Installed AND UILevel >= 4', 1230),
        ('MaintenanceDlg', 'Installed AND NOT REMOVE~="ALL" AND UILevel >= 4', 1230),
        ('RemoveDlg', 'Installed AND RemoveRequested AND UILevel >= 4', 1240),
        ('ProgressDlg', 'UILevel >= 4', 1280),
    ])
    m.add_data(db, 'InstallUISequence', rows)

    def page(name, title, first, default, cancel='Cancel', modeless=False, keep=False, caption='[WizardWindowTitle]'):
        attrs = (1 if modeless else 3) | (16 if keep else 0)
        d = m.Dialog(db, name, 50, 50, 370, 270, attrs, caption, first, default, cancel)
        d.control('Banner', 'Bitmap', 0, 0, 370, 56, 1, None, 'InstallerHeader', None, None)
        d.text('Heading', 22, 16, 286, 24, 65539, r'{\UiTitle}'+title)
        d.control('Icon', 'Bitmap', 322, 12, 30, 30, 1, None, 'InstallerIcon', None, None)
        d.line('HeaderLine', 0, 56, 370, 0)
        d.line('FooterLine', 0, 234, 370, 0)
        return d

    def button(d, name, label, x, next_name, event=None, arg=None, condition='1', y=243, width=56):
        b = d.pushbutton(name, x, y, width, 17, 3, label, next_name)
        if event:
            b.event(event, arg, condition, 1)
        return b

    def cancel(d, next_name):
        return button(d, 'Cancel', '取消(&C)', 304, next_name, 'EndDialog', 'Exit')

    welcome = page('WelcomeDlg', 'Enco Lite 安装向导', 'Next', 'Next')
    welcome.control('ProductIcon','Bitmap',20,77,44,44,1,None,'InstallerIcon',None,None)
    welcome.text('Product',82,78,250,22,3,r'{\UiTitle}Enco Lite')
    welcome.text('Version',82,104,250,18,3,'版本 [ProductRelease]')
    welcome.text('Intro',20,145,330,32,3,'将 Enco Lite 安装到此电脑。')
    welcome.pushbutton('License', 20, 188, 70, 18, 3, '许可证(&L)', 'Next').event('SpawnDialog', 'LicenseDlg', '1', 1)
    button(welcome, 'Next', '下一步(&N)', 236, 'Cancel', 'NewDialog', 'OptionsDlg')
    cancel(welcome, 'License')

    # Start on an enabled control even when an upgrade locks the folder fields.
    options = page('OptionsDlg', '安装选项', 'Install', 'Install')
    options.text('PathLabel', 20, 70, 330, 18, 3, '安装位置：')
    path = options.control('Path', 'PathEdit', 20, 93, 330, 20, 3, 'INSTALLDIR', None, 'Browse', None)
    browse = options.pushbutton('Browse', 20, 121, 70, 18, 3, '更改(&B)…', 'Desktop')
    browse.event('[_BrowseProperty]', 'INSTALLDIR', '1', 1)
    browse.event('SpawnDialog', 'BrowseDlg', '1', 2)
    for control in (path, browse):
        control.condition('Disable', 'OLDPRODUCTS OR Installed')
    options.text('UpgradeHint', 105, 122, 245, 18, 3, '升级将保留现有安装位置。').condition('Hide', 'NOT OLDPRODUCTS')
    options.checkbox('Desktop', 20, 166, 330, 20, 3, 'CREATE_DESKTOP_SHORTCUT', '创建桌面快捷方式(&D)', 'Back')
    button(options, 'Back', '上一步(&B)', 180, 'Install', 'NewDialog', 'WelcomeDlg')
    install = button(options, 'Install', '安装(&I)', 236, 'Cancel')
    install.event('SetTargetPath', 'INSTALLDIR', 'NOT OLDPRODUCTS AND NOT Installed', 1)
    install.event('EndDialog', 'Return', '1', 2)
    cancel(options, 'Path')

    folder = page('BrowseDlg', '选择文件夹', 'Folders', 'OK')
    folder.control('Folders', 'DirectoryCombo', 20, 66, 248, 20, 11, '_BrowseProperty', None, 'Up', None)
    folder.pushbutton('Up', 278, 66, 72, 20, 3, '上一级(&U)', 'List').event('DirectoryListUp', '0', '1', 1)
    folder.control('List', 'DirectoryList', 20, 96, 330, 104, 11, '_BrowseProperty', None, 'Path', None)
    folder.control('Path', 'PathEdit', 20, 208, 330, 18, 11, '_BrowseProperty', None, 'OK', None)
    ok = button(folder, 'OK', '确定', 236, 'Cancel')
    ok.event('SetTargetPath', '[_BrowseProperty]', '1', 1)
    ok.event('EndDialog', 'Return', '1', 2)
    button(folder, 'Cancel', '取消', 304, 'Folders', 'EndDialog', 'Return')

    maintenance = page('MaintenanceDlg', '更改 Enco Lite', 'Repair', 'Repair',caption='[ProductName] 更改安装')
    repair = button(maintenance, 'Repair', '修复(&R)', 20, 'Remove', y=78, width=80)
    maintenance.text('RepairText', 116, 78, 234, 34, 3, '重新安装缺失或损坏的程序文件。')
    repair.event('[REMOVE]', '{}', '1', 1)
    repair.event('[REINSTALL]', 'ALL', '1', 2)
    repair.event('[REINSTALLMODE]', 'amus', '1', 3)
    repair.event('[WizardProgressTitle]', '正在修复', '1', 4)
    repair.event('[WizardFinishTitle]', '修复完成', '1', 5)
    repair.event('EndDialog', 'Return', '1', 6)
    button(maintenance, 'Remove', '卸载(&U)', 20, 'Cancel', 'NewDialog', 'RemoveDlg', y=137, width=80)
    maintenance.text('RemoveText', 116, 137, 234, 34, 3, '从此电脑移除 Enco Lite。')
    button(maintenance, 'Cancel', '关闭(&C)', 304, 'Repair', 'EndDialog', 'Exit')

    remove = page('RemoveDlg', '卸载 Enco Lite', 'Cancel', 'Cancel',caption='[ProductName] 卸载程序')
    remove.control('ProductIcon','Bitmap',20,77,44,44,1,None,'InstallerIcon',None,None)
    remove.text('Product',82,78,250,22,3,r'{\UiTitle}Enco Lite')
    remove.text('Version',82,104,250,18,3,'版本 [ProductRelease]')
    remove.text('Intro',20,145,330,22,3,'将从此电脑卸载 Enco Lite。')
    remove.text('Settings',20,177,330,40,3,'个人设置和耳机配对将保留。\r\n开机自启动项将一并移除。')
    back = button(remove, 'Back', '上一步(&B)', 180, 'Remove')
    back.event('[REMOVE]', '{}', '1', 1)
    back.event('NewDialog', 'MaintenanceDlg', '1', 2)
    uninstall = button(remove, 'Remove', '卸载(&U)', 236, 'Cancel')
    uninstall.event('[REINSTALL]', '{}', '1', 1)
    uninstall.event('[REMOVE]', 'ALL', '1', 2)
    uninstall.event('[LAUNCH_AFTER_INSTALL]', '{}', '1', 3)
    uninstall.event('[WizardProgressTitle]', '正在卸载', '1', 4)
    uninstall.event('[WizardFinishTitle]', '卸载完成', '1', 5)
    uninstall.event('[WizardWindowTitle]', 'Enco Lite 卸载程序', '1', 6)
    uninstall.event('EndDialog', 'Return', '1', 7)
    cancel(remove, 'Back')

    progress = page('ProgressDlg', '[WizardProgressTitle]', 'Cancel', 'Cancel', modeless=True)
    progress.text('Action', 20, 82, 330, 22, 3, '正在准备…').mapping('ActionText', 'Text')
    progress.control('Progress', 'ProgressBar', 20, 119, 330, 12, 1, None, None, None, None).mapping('SetProgress', 'Progress')
    progress.text('Detail', 20, 151, 330, 48, 131075, '').mapping('ActionData', 'Text')
    cancel(progress, 'Cancel')

    done = page('ExitDialog', '[WizardFinishTitle]', 'Finish', 'Finish', 'Finish')
    done.text('Installed', 20, 78, 330, 30, 3, 'Enco Lite 已安装。').condition('Hide', 'REMOVE~="ALL" OR REINSTALL')
    done.text('Repaired', 20, 78, 330, 30, 3, 'Enco Lite 已修复。').condition('Hide', 'REMOVE~="ALL" OR NOT REINSTALL')
    done.text('Removed', 20, 78, 330, 30, 3, 'Enco Lite 已卸载。').condition('Hide', 'NOT REMOVE~="ALL"')
    done.checkbox('Launch', 20, 133, 330, 20, 3, 'LAUNCH_AFTER_INSTALL', '运行 Enco Lite(&L)', 'Finish').condition('Hide', 'REMOVE~="ALL"')
    finish = button(done, 'Finish', '完成(&F)', 304, 'Launch')
    finish.event('DoAction', 'SetLauncher', 'LAUNCH_AFTER_INSTALL=1 AND NOT REMOVE~="ALL"', 1)
    finish.event('DoAction', 'LaunchApplication', 'LAUNCH_AFTER_INSTALL=1 AND NOT REMOVE~="ALL"', 2)
    finish.event('EndDialog', 'Return', '1', 3)

    for name, title, body in [
        ('FatalError', '操作未完成', '未能完成操作。请重试，或查看日志。\r\n\r\n[MsiLogFileLocation]'),
        ('UserExit', '已取消', '操作未完成。'),
    ]:
        d = page(name, title, 'Close', 'Close', 'Close')
        d.text('Body', 20, 78, 330, 130, 131075, body)
        button(d, 'Close', '关闭', 304, 'Close', 'EndDialog', 'Return')

    license = page('LicenseDlg', '许可证', 'Close', 'Close', 'Close')
    text = (root/'LICENSE').read_text('utf-8').replace('\\', r'\\').replace('{', r'\{').replace('}', r'\}').replace('\n', r'\par ')
    license.control('Text', 'ScrollableText', 20, 64, 330, 158, 3, None, r'{\rtf1\ansi\deff0{\fonttbl{\f0 Segoe UI;}}\f0\fs16 '+text+'}', None, None)
    button(license, 'Close', '关闭', 304, 'Close', 'EndDialog', 'Return')

    in_use = page('FilesInUse', '文件正在使用', 'Retry', 'Retry', 'Cancel', keep=True)
    in_use.text('Intro', 20, 65, 330, 36, 3, '请关闭以下程序，然后点击“重试”。')
    in_use.control('List', 'ListBox', 20, 110, 330, 104, 7, 'FileInUseProcess', None, None, None)
    button(in_use, 'Retry', '重试(&R)', 236, 'Cancel', 'EndDialog', 'Retry')
    cancel(in_use, 'Retry')

    rm = page('MsiRMFilesInUse', '关闭正在使用的程序', 'Options', 'OK', keep=True)
    rm.text('Intro', 20, 65, 330, 28, 3, '以下程序正在使用 Enco Lite 文件。')
    rm.control('List', 'ListBox', 20, 99, 330, 69, 7, 'FileInUseProcess', None, None, None)
    rm.control('Options', 'RadioButtonGroup', 20, 177, 330, 43, 3, 'RMCHOICE', None, 'OK', None)
    m.add_data(db, 'RadioButton', [
        ('RMCHOICE', 1, 'Close', 0, 0, 330, 16, '自动关闭程序并继续(&A)', None),
        ('RMCHOICE', 2, 'Manual', 0, 23, 330, 16, '稍后重新启动电脑(&L)', None),
    ])
    ok = button(rm, 'OK', '继续', 236, 'Cancel')
    ok.event('RMShutdownAndRestart', '0', 'RMCHOICE="Close"', 1)
    ok.event('EndDialog', 'Return', '1', 2)
    cancel(rm, 'Options')

    error = m.Dialog(db, 'ErrorDlg', 50, 50, 370, 160, 65539, '[ProductName]', 'ErrorText', None, None)
    error.text('ErrorText', 20, 16, 330, 100, 3, '')
    for name, label in [('Ok', '确定'), ('Cancel', '取消'), ('Abort', '终止'), ('Retry', '重试'), ('Ignore', '忽略'), ('Yes', '是'), ('No', '否')]:
        error.pushbutton(name, 155, 130, 56, 17, 3, label, None).event('EndDialog', 'Error'+name, '1', 1)
