//
//  kern_tr.cpp
//  TerascaleRed
//
//  Phase 0: observe. Finds the TeraScale iGPU by its config-space ID (so a spoofed device-id doesn't hide it), logs
//  what the hardware reports and publishes it in the I/O Registry. Nothing is patched yet.
//
//  Patterns follow CarrizoRed and KaberiRed (same author, BSD-3).
//

#include "kern_tr.hpp"

#include <Headers/kern_api.hpp>
#include <Headers/kern_devinfo.hpp>
#include <Headers/kern_iokit.hpp>
#include <Headers/kern_util.hpp>
#include <IOKit/IODeviceTreeSupport.h>

void TRDriver::init() {
	SYSLOG("tr", "TerascaleRed starting on kernel %d.%d", getKernelVersion(), getKernelMinorVersion());
	lilu.onPatcherLoadForce(
		[](void *user, KernelPatcher &patcher) { static_cast<TRDriver *>(user)->processPatcher(patcher); }, this);
}

bool TRDriver::consider(IOPCIDevice *pci) {
	if (!pci)
		return false;
	auto vendor = WIOKit::readPCIConfigValue(pci, WIOKit::kIOPCIConfigVendorID);
	auto device = static_cast<uint16_t>(WIOKit::readPCIConfigValue(pci, WIOKit::kIOPCIConfigDeviceID));
	if (vendor != WIOKit::VendorID::ATIAMD || familyForDevice(device) == ChipFamily::Unknown)
		return false;
	iGPU = pci;
	iGPU->retain();
	family = familyForDevice(device);
	deviceId = device;
	return true;
}

void TRDriver::processPatcher(KernelPatcher &patcher) {
	if (auto *devInfo = DeviceInfo::create()) {
		// Once device-id is spoofed to a dGPU's, Lilu lists the iGPU under videoExternal: check both.
		if (!consider(OSDynamicCast(IOPCIDevice, devInfo->videoBuiltin)))
			for (size_t i = 0; i < devInfo->videoExternal.size(); i++)
				if (consider(OSDynamicCast(IOPCIDevice, devInfo->videoExternal[i].video)))
					break;
		DeviceInfo::deleter(devInfo);
	}
	if (!iGPU)
		findByConfigSpace();
	if (!iGPU) {
		SYSLOG("tr", "no supported TeraScale iGPU found, disabling");
		return;
	}
	logPCIInfo();
	if (!checkKernelArgument("-trnommio"))
		probeMMIO();
}

void TRDriver::findByConfigSpace() {
	// DeviceInfo skips devices whose vendor-id property isn't a known GPU vendor; walk the device tree instead.
	auto *iterator = IORegistryIterator::iterateOver(gIODTPlane, kIORegistryIterateRecursively);
	if (!iterator)
		return;
	while (auto *entry = iterator->getNextObject()) {
		if (consider(OSDynamicCast(IOPCIDevice, entry))) {
			SYSLOG("tr", "found iGPU %s by config space (not listed by DeviceInfo)", safeString(iGPU->getName()));
			break;
		}
	}
	iterator->release();
}

void TRDriver::logPCIInfo() {
	revision = static_cast<uint8_t>(WIOKit::readPCIConfigValue(iGPU, WIOKit::kIOPCIConfigRevisionID));
	auto subVendor =
		static_cast<uint16_t>(WIOKit::readPCIConfigValue(iGPU, WIOKit::kIOPCIConfigSubSystemVendorID, 0, 16));
	auto subDevice = static_cast<uint16_t>(WIOKit::readPCIConfigValue(iGPU, WIOKit::kIOPCIConfigSubSystemID, 0, 16));
	uint32_t propDeviceId = 0;
	WIOKit::getOSDataValue(iGPU, "device-id", propDeviceId);
	SYSLOG("tr", "found %s iGPU at %s: 1002:%04X rev 0x%02X subsys %04X:%04X (device-id property 0x%04X), %s",
		familyName(family), safeString(iGPU->getName()), deviceId, revision, subVendor, subDevice,
		propDeviceId & 0xFFFF, isVLIW4(family) ? "VLIW4" : "VLIW5");
	iGPU->setProperty("TerascaleRed,family", familyName(family));
	iGPU->setProperty("TerascaleRed,revision", revision, 8);
}

void TRDriver::probeMMIO() {
	// Evergreen/NI-era chips put the registers in BAR2 (radeon: rmmio_base = BAR 2 before Bonaire).
	auto *map = iGPU->mapDeviceMemoryWithRegister(kIOPCIConfigBaseAddress2);
	if (!map) {
		SYSLOG("tr", "failed to map the MMIO BAR, skipping the register probe");
		return;
	}
	auto *mmio = reinterpret_cast<volatile uint32_t *>(map->getVirtualAddress());
	uint32_t memSize = mmio[Reg::CONFIG_MEMSIZE];
	uint32_t fbLocation = mmio[Reg::MC_VM_FB_LOCATION];
	SYSLOG("tr", "CONFIG_MEMSIZE 0x%08X MC_VM_FB_LOCATION 0x%08X MC_SHARED_CHMAP 0x%08X MC_ARB_RAMCFG 0x%08X", memSize,
		fbLocation, mmio[Reg::MC_SHARED_CHMAP], mmio[Reg::MC_ARB_RAMCFG]);
	SYSLOG("tr", "GRBM_STATUS 0x%08X SRBM_STATUS 0x%08X GB_ADDR_CONFIG 0x%08X CC_GC_SHADER_PIPE_CONFIG 0x%08X "
		"CC_RB_BACKEND_DISABLE 0x%08X", mmio[Reg::GRBM_STATUS], mmio[Reg::SRBM_STATUS], mmio[Reg::GB_ADDR_CONFIG],
		mmio[Reg::CC_GC_SHADER_PIPE_CONFIG], mmio[Reg::CC_RB_BACKEND_DISABLE]);
	for (uint32_t pipe = 0; pipe < 2; pipe++) {
		uint32_t r = pipeRegisterBase(pipe);
		SYSLOG("tr", "pipe %u: CRTC_CONTROL 0x%08X GRPH_ENABLE 0x%08X surface 0x%08X%08X pitch %u", pipe,
			mmio[Reg::CRTC_CONTROL + r], mmio[Reg::GRPH_ENABLE + r], mmio[Reg::GRPH_PRIMARY_SURFACE_ADDRESS_HIGH + r],
			mmio[Reg::GRPH_PRIMARY_SURFACE_ADDRESS + r], mmio[Reg::GRPH_PITCH + r]);
	}
	iGPU->setProperty("TerascaleRed,config-memsize", memSize, 32);
	iGPU->setProperty("TerascaleRed,fb-location", fbLocation, 32);
	iGPU->setProperty("TerascaleRed,gb-addr-config", mmio[Reg::GB_ADDR_CONFIG], 32);
	map->release();
}
