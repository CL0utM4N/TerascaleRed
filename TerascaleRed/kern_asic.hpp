//
//  kern_asic.hpp
//  TerascaleRed
//
//  Hardware constants for the TeraScale APUs: Llano (Sumo/SuperSumo), Brazos (Palm) and Trinity/Richland (Aruba).
//  PCI IDs from Linux include/drm/drm_pciids.h; register offsets from drivers/gpu/drm/radeon/evergreend.h, nid.h and
//  evergreen_reg.h (MIT licensed), as dword indices into the MMIO BAR (BAR2 on these chips).
//

#ifndef kern_asic_hpp
#define kern_asic_hpp

#include <stdint.h>
#include <stddef.h>

enum class ChipFamily {
	Unknown,
	Sumo,      // Llano, HD 6xxxD/G with 5 SIMDs ("SUMO" in Apple's CAIL): TeraScale 2 (VLIW5), DCE 4.1
	SuperSumo, // Llano, smaller GPUs ("SUPERSUMO" in Apple's CAIL, CHIP_SUMO2 in Linux): TeraScale 2, DCE 4.1
	Palm,      // Brazos/Ontario/Zacate ("WRESTLER" in Apple's CAIL): TeraScale 2, DCE 4.1
	Aruba,     // Trinity/Richland ("DEVASTATOR"/"SCRAPPER" in Apple's CAIL): TeraScale 3 (VLIW4), DCE 6.1
};

struct DeviceId {
	uint16_t id;
	ChipFamily family;
};

static constexpr DeviceId SupportedDevices[] {
	{0x9640, ChipFamily::Sumo}, {0x9641, ChipFamily::Sumo}, {0x9647, ChipFamily::Sumo}, {0x9648, ChipFamily::Sumo},
	{0x964A, ChipFamily::Sumo}, {0x964B, ChipFamily::Sumo}, {0x964C, ChipFamily::Sumo}, {0x964E, ChipFamily::Sumo},
	{0x964F, ChipFamily::Sumo},
	{0x9642, ChipFamily::SuperSumo}, {0x9643, ChipFamily::SuperSumo}, {0x9644, ChipFamily::SuperSumo},
	{0x9645, ChipFamily::SuperSumo}, {0x9649, ChipFamily::SuperSumo},
	{0x9802, ChipFamily::Palm}, {0x9803, ChipFamily::Palm}, {0x9804, ChipFamily::Palm}, {0x9805, ChipFamily::Palm},
	{0x9806, ChipFamily::Palm}, {0x9807, ChipFamily::Palm}, {0x9808, ChipFamily::Palm}, {0x9809, ChipFamily::Palm},
	{0x980A, ChipFamily::Palm},
	{0x9900, ChipFamily::Aruba}, {0x9901, ChipFamily::Aruba}, {0x9903, ChipFamily::Aruba}, {0x9904, ChipFamily::Aruba},
	{0x9905, ChipFamily::Aruba}, {0x9906, ChipFamily::Aruba}, {0x9907, ChipFamily::Aruba}, {0x9908, ChipFamily::Aruba},
	{0x9909, ChipFamily::Aruba}, {0x990A, ChipFamily::Aruba}, {0x990B, ChipFamily::Aruba}, {0x990C, ChipFamily::Aruba},
	{0x990D, ChipFamily::Aruba}, {0x990E, ChipFamily::Aruba}, {0x990F, ChipFamily::Aruba}, {0x9910, ChipFamily::Aruba},
	{0x9913, ChipFamily::Aruba}, {0x9917, ChipFamily::Aruba}, {0x9918, ChipFamily::Aruba}, {0x9919, ChipFamily::Aruba},
	{0x9990, ChipFamily::Aruba}, {0x9991, ChipFamily::Aruba}, {0x9992, ChipFamily::Aruba}, {0x9993, ChipFamily::Aruba},
	{0x9994, ChipFamily::Aruba}, {0x9995, ChipFamily::Aruba}, {0x9996, ChipFamily::Aruba}, {0x9997, ChipFamily::Aruba},
	{0x9998, ChipFamily::Aruba}, {0x9999, ChipFamily::Aruba}, {0x999A, ChipFamily::Aruba}, {0x999B, ChipFamily::Aruba},
	{0x999C, ChipFamily::Aruba}, {0x999D, ChipFamily::Aruba}, {0x99A0, ChipFamily::Aruba}, {0x99A2, ChipFamily::Aruba},
	{0x99A4, ChipFamily::Aruba},
};

inline ChipFamily familyForDevice(uint16_t deviceId) {
	for (auto &dev : SupportedDevices)
		if (dev.id == deviceId)
			return dev.family;
	return ChipFamily::Unknown;
}

inline const char *familyName(ChipFamily family) {
	switch (family) {
		case ChipFamily::Sumo:
			return "Llano (Sumo)";
		case ChipFamily::SuperSumo:
			return "Llano (SuperSumo)";
		case ChipFamily::Palm:
			return "Brazos (Palm)";
		case ChipFamily::Aruba:
			return "Trinity/Richland (Aruba)";
		default:
			return "Unknown";
	}
}

// The shader ISA the GPU runs: what Apple's compiler must emit for it.
inline bool isVLIW4(ChipFamily family) { return family == ChipFamily::Aruba; }

namespace Reg {
	// Byte offsets / 4. Same on Evergreen, Northern Islands and these APUs unless noted.
	static constexpr uint32_t SRBM_STATUS = 0x0E50 / 4;
	static constexpr uint32_t MC_SHARED_CHMAP = 0x2004 / 4;
	static constexpr uint32_t MC_VM_FB_LOCATION = 0x2024 / 4;
	static constexpr uint32_t MC_ARB_RAMCFG = 0x2760 / 4;
	static constexpr uint32_t CONFIG_MEMSIZE = 0x5428 / 4;
	static constexpr uint32_t GRBM_STATUS = 0x8010 / 4;
	static constexpr uint32_t CC_GC_SHADER_PIPE_CONFIG = 0x8950 / 4;
	static constexpr uint32_t CC_RB_BACKEND_DISABLE = 0x98F4 / 4;
	static constexpr uint32_t GB_ADDR_CONFIG = 0x98F8 / 4;
	// DCE 4.x/6.x display pipe registers, pipe 0; add pipeRegisterBase(pipe).
	static constexpr uint32_t GRPH_ENABLE = 0x6800 / 4;
	static constexpr uint32_t GRPH_PRIMARY_SURFACE_ADDRESS = 0x6810 / 4;
	static constexpr uint32_t GRPH_PITCH = 0x6818 / 4;
	static constexpr uint32_t GRPH_PRIMARY_SURFACE_ADDRESS_HIGH = 0x681C / 4;
	static constexpr uint32_t CRTC_CONTROL = 0x6E70 / 4;
}

// Every family here has at least two pipes; pipe 1 sits 0xC00 bytes after pipe 0 (evergreen_reg.h).
inline uint32_t pipeRegisterBase(uint32_t pipe) { return pipe == 0 ? 0 : (0x79F0 - 0x6DF0) / 4; }

#endif /* kern_asic_hpp */
