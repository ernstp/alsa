from utils import git_popen, git_system, git_repo, is_alsa_file, to_alsa_file, \
                 filecheck=is_alsa_file, fileconv=to_alsa_file):
        src = git_repo(driver_repo) + '/' + to_alsa_file(f)
                 filecheck=is_alsa_file, fileconv=to_alsa_file,
    if ref == '03510ca07ad48941072d673321d2b009be6dfcd4':
      return False
                       '6539799', '152a3a7', '79980d9', \
                       '2955b47', '5daf53a', '5e70b7f', \
                       '2203747', '04564e3', '946cc36', \
                       '07b706d', '68214d9', '257d36f', \
                       'ab6340c', '6cab3e1', '0875eb7', \
                       '54f6019', '31a62d4', 'fc48851', \
                       '559c200', 'ec6f432', '617ade6', \
                       'e043403', 'a06e427', 'acc8da7', \
                       '59b5645', '338c658', 'e9a7495', \
                       'db8d3af', '9a199b8', '05004cb', \
                       'c28b14f', '03510ca', '6489573', \
                       'e95d73c', 'd8f6479', '2488708', \
                       'de0d712', '88d5e52']:
        print 'Press Enter to continue and skip this path, or press Ctrl-C to abort'
        stdin.readline()
        if ref[:7] in ['617ade6', 'd8f6479', '0799958', 'ed520c9', 'bdfbf25', 'e948262', '5c2b063']:
          print '  It is probably OK...'
          return False
        print 'Press Enter to continue and skip this path, or press Ctrl-C to abort'
        stdin.readline()
    if addfiles and git_system(driver_repo, "add -f %s" % ' '.join(addfiles)):
    if git_system(driver_repo, "archive --format=tar %s | tar xf - -C %s" % (driver_branch, worktree)):
    if git_system(kernel_repo, "archive --format=tar %s sound include/sound include/uapi/sound include/dt-bindings/sound Documentation/sound Documentation/devicetree/bindings/sound | tar xf - -C %s" % (kernel_branch, worktreek)):
    #
    oklist = []
    for f in listdir("alsa-driver-repo/Documentation/devicetree/bindings/sound/"):
      if not f in ['.', '..']:
        oklist.append(f)
    for f in listdir("alsa-kernel-repo/Documentation/devicetree/bindings/sound/"):
      if not f in ['.', '..'] and not f in oklist:
        remove('alsa-kernel-repo/Documentation/devicetree/bindings/sound/' + f)
    #
    remove("alsa-driver-repo/.gitignore")
    rmtree("alsa-driver-repo/sound/oss")
    rmtree("alsa-driver-repo/scripts")
    #remove("alsa-kernel-repo/.gitignore")
    rmtree("alsa-kernel-repo/Documentation/sound/oss")
      for i in ['oss', 'Documentation/sound/oss',
                'pci/ac97/ak4531_codec.c', 'isa/sb/sb16_csp_codecs.h',
                'isa/wavefront/yss225.c',
                'sound/soc/intel/common/sst-acpi.c',
                'sound/soc/intel/common/sst-dsp.c',
                'sound/soc/intel/common/sst-dsp.h',
                'sound/soc/intel/common/sst-dsp-priv.h',
                'sound/soc/intel/common/sst-firmware.c',
    fp = popen("diff -ruNp alsa-driver-repo alsa-kernel-repo")