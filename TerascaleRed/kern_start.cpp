//
//  kern_start.cpp
//  TerascaleRed
//

#include <Headers/kern_api.hpp>
#include <Headers/plugin_start.hpp>

#include "kern_tr.hpp"

static TRDriver tr;

static const char *bootargOff[] {"-troff"};
static const char *bootargDebug[] {"-trdbg"};
static const char *bootargBeta[] {"-trbeta"};

// El Capitan (10.11) through High Sierra (10.13): the releases that ship Apple's TeraScale 2 drivers (AMDRadeonX3000)
// and, for Llano, still have SSSE3-emulating AMD kernels. -trbeta runs outside that range.
PluginConfiguration ADDPR(config) {
	xStringify(PRODUCT_NAME),
	parseModuleVersion(xStringify(MODULE_VERSION)),
	LiluAPI::AllowNormal | LiluAPI::AllowInstallerRecovery | LiluAPI::AllowSafeMode,
	bootargOff,
	arrsize(bootargOff),
	bootargDebug,
	arrsize(bootargDebug),
	bootargBeta,
	arrsize(bootargBeta),
	KernelVersion::ElCapitan,
	KernelVersion::HighSierra,
	[]() { tr.init(); },
};
