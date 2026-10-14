#!/usr/bin/env python3
"""Build an isolated Android NativeActivity Vulkan surface benchmark APK.

Only WSA x86_64. Never packages Call of Duty assets, changes game APK, or
implements a CoDSP renderer. All APK, signing and log outputs stay .local.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import os
import subprocess
import sys
import re
import zipfile

ROOT=Path(__file__).resolve().parents[3]
SOURCE=ROOT/'tools/recomp/diagnostics/wsa_vk_surface_bench.c'
MESH_SOURCE=ROOT/'tools/recomp/diagnostics/wsa_vk_mesh.c'
TEXTURE_SOURCE=ROOT/'tools/recomp/diagnostics/wsa_vk_texture.c'
DEPTH_SOURCE=ROOT/'tools/recomp/diagnostics/wsa_vk_depth.c'
GL_STATE_SOURCE=ROOT/'tools/recomp/runtime/gl_vk_state.c'
GL_STATE_MAP_SOURCE=ROOT/'tools/recomp/diagnostics/wsa_vk_gl_state_map.c'
SHADERS=ROOT/'tools/recomp/diagnostics/shaders'
PACKAGE='org.rigorcore.vkswapbench'

def run(*args):
    result=subprocess.run([str(x) for x in args],check=True,capture_output=True,text=True,timeout=150)
    if result.stdout.strip():print(result.stdout[-1100:],flush=True)
    if result.stderr.strip():print(result.stderr[-900:],flush=True)

def latest(root: Path) -> Path:
    dirs=[x for x in root.iterdir() if x.is_dir()]
    if not dirs:raise RuntimeError('Missing Android SDK component '+str(root))
    return max(dirs,key=lambda x:tuple(int(part) for part in re.findall(r'\d+',x.name)))

def main():
    ap=argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--present',choices=['fifo','immediate'],default='fifo')
    ap.add_argument('--scene',choices=['clear','mesh','texture','depth','alpha','matrix'],default='clear',
                    help='isolated clear baseline or real indexed Vulkan mesh; not game FPS')
    ap.add_argument('--sdk',type=Path,default=os.environ.get('ANDROID_HOME'))
    args=ap.parse_args()
    if not args.sdk:ap.error('--sdk or ANDROID_HOME is required')
    sdk=Path(args.sdk)
    ndk=latest(sdk/'ndk')
    bt=latest(sdk/'build-tools')
    jar=latest(sdk/'platforms')/'android.jar'
    java=Path(os.environ.get('JAVA_HOME','C:/Program Files/Java/jdk-17'))
    dest=ROOT/'.local/profiles/wsa_vulkan_ab'/(args.present if args.scene=='clear' else args.scene+'-'+args.present)
    dest.mkdir(parents=True,exist_ok=True)
    manifest=dest/'AndroidManifest.xml'
    manifest.write_text("""<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android"
    package="org.rigorcore.vkswapbench">
    <uses-sdk android:minSdkVersion="28" android:targetSdkVersion="28" />
    <uses-feature android:name="android.hardware.vulkan.version"
        android:version="0x400000" android:required="false"/>
    <application android:label="Vk Surface Bench"
        android:hasCode="false" android:theme="@android:style/Theme.Material.NoActionBar.Fullscreen">
        <activity android:name="android.app.NativeActivity"
            android:exported="true"
            android:configChanges="orientation|keyboardHidden|screenSize">
            <meta-data android:name="android.app.lib_name" android:value="vk_swap_bench" />
            <intent-filter>
                <action android:name="android.intent.action.MAIN"/>
                <category android:name="android.intent.category.LAUNCHER"/>
            </intent-filter>
        </activity>
    </application>
</manifest>
""",encoding='utf-8')
    exe='x86_64-linux-android28-clang.cmd' if os.name=='nt' else 'x86_64-linux-android28-clang'
    clang=ndk/'toolchains/llvm/prebuilt/windows-x86_64/bin'/exe
    so=dest/'libvk_swap_bench.so'
    print('Compiling Vulkan NativeActivity',args.present,args.scene,flush=True)
    srcs=[SOURCE]
    shader_bins=[]
    if args.scene in ('mesh','texture','depth','alpha','matrix'):
        srcs.append(MESH_SOURCE)
        srcs.append(TEXTURE_SOURCE)
        if args.scene=='depth':
            srcs.extend([DEPTH_SOURCE,GL_STATE_SOURCE,GL_STATE_MAP_SOURCE])
        elif args.scene in ('alpha','matrix'):
            srcs.append(GL_STATE_SOURCE)
        compiler=ndk/'shader-tools/windows-x86_64/glslc.exe'
        validator=ndk/'shader-tools/windows-x86_64/spirv-val.exe'
        if not compiler.is_file() or not validator.is_file():
            raise RuntimeError('NDK glslc and spirv-val are required for mesh scene')
        for stage in ('vert','frag'):
            name=('wsa_matrix.vert' if stage=='vert' and args.scene=='matrix' else
                  'wsa_alpha.frag' if stage=='frag' and args.scene=='alpha' else
                  'wsa_texture.frag' if stage=='frag' and args.scene in ('texture','depth') else
                  'wsa_mesh.'+stage)
            shader=SHADERS/name
            target=dest/(name+'.spv')
            run(compiler,'--target-env=vulkan1.0',shader,'-o',target)
            run(validator,'--target-env','vulkan1.0',target)
            shader_bins.append(target)
        if args.scene=='depth':
            overlay_shader=SHADERS/'wsa_overlay.frag'
            overlay_binary=dest/'wsa_overlay.frag.spv'
            run(compiler,'--target-env=vulkan1.0',overlay_shader,'-o',overlay_binary)
            run(validator,'--target-env','vulkan1.0',overlay_binary)
            shader_bins.append(overlay_binary)
    run(clang,'-O2','-std=c11','-Wall','-Wextra','-Werror',
        '-D_POSIX_C_SOURCE=200809L',
        f'-DVK_BENCH_PREFER_IMMEDIATE={int(args.present=="immediate")}',
        f'-DVK_BENCH_MESH_SCENE={int(args.scene in ("mesh","texture","depth","alpha","matrix"))}',
        f'-DVK_BENCH_TEXTURE_SCENE={int(args.scene in ("texture","depth","alpha"))}',
        f'-DVK_BENCH_DEPTH_SCENE={int(args.scene=="depth")}',
        f'-DVK_BENCH_ALPHA_SCENE={int(args.scene=="alpha")}',
        f'-DVK_BENCH_MATRIX_SCENE={int(args.scene=="matrix")}',
        '-shared','-fPIC','-Wl,-z,max-page-size=16384',
        *srcs,'-o',so,'-lvulkan','-landroid','-llog','-lm','-pthread')
    aapt=bt/('aapt2.exe' if os.name=='nt' else 'aapt2')
    unsigned=dest/'unsigned.apk'
    run(aapt,'link','-I',jar,'--manifest',manifest,'-o',unsigned)
    with zipfile.ZipFile(unsigned,'a') as apk:
        apk.write(so,'lib/x86_64/libvk_swap_bench.so',compress_type=zipfile.ZIP_STORED)
        for binfile in shader_bins:
            apk.write(binfile,'assets/'+binfile.name,compress_type=zipfile.ZIP_STORED)
    aligned=dest/'aligned.apk'
    zipalign=bt/('zipalign.exe' if os.name=='nt' else 'zipalign')
    run(zipalign,'-f','-P','16','4',unsigned,aligned)
    keystore=ROOT/'build-android-package/debug.keystore'
    if not keystore.is_file():
        raise RuntimeError('Existing local debug keystore missing; refusing to create one')
    apk=dest/('wsa-vulkan-'+args.present+('-'+args.scene if args.scene!='clear' else '')+'.apk')
    signer=bt/('apksigner.bat' if os.name=='nt' else 'apksigner')
    run(signer,'sign','--ks',keystore,'--ks-key-alias','androiddebugkey',
        '--ks-pass','pass:android','--key-pass','pass:android','--out',apk,aligned)
    run(signer,'verify','--verbose',apk)
    print('BUILT',apk,'bytes',apk.stat().st_size,flush=True)

if __name__=='__main__':
    main()
