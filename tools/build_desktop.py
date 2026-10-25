"""Build the window process; the production tray never loads this runtime."""
from pathlib import Path
import os,subprocess
ROOT=Path(__file__).resolve().parents[1]


def build():
    sdk=ROOT.parent/'构建工具/dotnet-10.0.302/dotnet.exe'
    env={**os.environ,'DOTNET_CLI_TELEMETRY_OPTOUT':'1','DOTNET_NOLOGO':'1',
        'DOTNET_SKIP_FIRST_TIME_EXPERIENCE':'1','DOTNET_GENERATE_ASPNET_CERTIFICATE':'false',
        'DOTNET_CLI_HOME':str(ROOT.parent/'构建工具/cli-home'),
        'NUGET_PACKAGES':str(Path(os.environ['USERPROFILE'])/'.nuget/packages')}
    subprocess.run([str(sdk),'publish',str(ROOT/'desktop/EncoLite.Desktop.csproj'),'-c','Release',
        '-r','win-x64','--self-contained','false','--nologo','--ignore-failed-sources',
        '-p:UseSharedCompilation=false'],check=True,env=env)
    return ROOT/'desktop/bin/Release/net10.0/win-x64/publish'

if __name__=='__main__':print(build(),flush=True)
