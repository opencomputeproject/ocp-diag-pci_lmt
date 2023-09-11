# (c) Meta Platforms, Inc. and affiliates.
# Use of this source code is governed by an MIT-style
# license that can be found in the LICENSE file or at
# https://opensource.org/licenses/MIT.

from unittest import mock

import testslide

from . import pci_lib


class TestPciLib(testslide.TestCase):
    def setUp(self) -> None:
        self.pci_lib = pci_lib.PciLib("0000:11:2.3")
        super().setUp()

    def test_read_fails_invalid_args(self) -> None:
        """Tests if read method fails when invalid args are given."""
        # Invalid address.
        self.assertEqual(self.pci_lib.read(address=0xFFFF), -1)
        # Invalid width.
        self.assertEqual(self.pci_lib.read(address=0xFF, width=64), -1)
        # Unknown exception with valid address & val.
        with mock.patch("os.popen", side_effect=BaseException):
            self.assertEqual(self.pci_lib.read(address=0xFF, width=32), -1)

    @mock.patch("os.popen", new_callable=mock.mock_open, read_data="ABCD1234")
    def test_read(self, mock_popen) -> None:
        """Tests if read method works when valid args are given."""
        self.assertEqual(self.pci_lib.read(address=0xFF, width=32), 0xABCD1234)

    def test_write_fails_invalid_args(self) -> None:
        """Tests if write method fails when invalid args are given."""
        # Invalid address.
        self.assertEqual(self.pci_lib.write(address=0xFFFF, data=0), -1)
        # Invalid width.
        self.assertEqual(self.pci_lib.write(address=0xFF, data=0, width=64), -1)
        # Unknown exception with valid address & val.
        with mock.patch("os.popen", side_effect=BaseException):
            self.assertEqual(self.pci_lib.write(address=0xFF, data=0, width=32), -1)

    @mock.patch("os.popen", new_callable=mock.mock_open)
    def test_write(self, mock_popen) -> None:
        """Tests if write method works when valid args are given."""
        self.assertEqual(self.pci_lib.write(address=0xFF, data=0, width=32), 0)

    def test_create_dict_capabilities(self) -> None:
        """Tests if capabilities dict can be created."""
        # Register values are of the format (bits): xxxx_xVVV_NNNN_NNNN_IIII_IIII
        # Where: I[0..7]->ID, N[8..15]->NextPtr, V[16..18]->Version, x->Dont'care.
        with mock.patch.object(self.pci_lib, "read", side_effect=[0x1000, 0x200A, 0x300B, 0]):
            self.pci_lib.create_dict_capabilities()
            self.assertEqual(list(self.pci_lib.cap_dict.keys()), [0xA, 0xB, 0])

    def test_create_dict_ext_capabilities(self) -> None:
        """Tests if extended capabilities dict can be created."""
        # Register values are of the format (bits): NNNN_NNNN_NNNN_VVVV_IIII_IIII_IIII_IIII
        # Where: I[0..15]->ID, V[16..19]->Version, N[20..31]->NextPtr
        with mock.patch.object(self.pci_lib, "read", side_effect=[0x10A000, 0x20B000, 0]):
            self.pci_lib.create_dict_extended_capabilities()
            self.assertEqual(list(self.pci_lib.ext_cap_dict.keys()), [0xA000, 0xB000, 0])

    def test_get_link_status(self) -> None:
        """Tests if get_link_status method works."""
        # Setup reads to return PCIE_EXPRESS_CAP_ID as 0x10.
        # Return Speed as 16GT/s and width as 32.
        with mock.patch.object(self.pci_lib, "read", side_effect=[0x1000, 0x2010, 0, 0x204]):
            self.assertEqual(
                self.pci_lib.get_link_status(),
                pci_lib.LinkStatusInfo(err_msg=None, speed=4, speed_gts="16GT/s", width=32),
            )

    def test_get_lmt_cap_info(self) -> None:
        """Tests if getting LMT Capability Info works."""
        # Setup reads to return PCI_LMT_EXT_CAP_ID (0x27) at offset EXTENDED_CAPABILITIES_POINTER (0x100).
        with mock.patch.object(self.pci_lib, "read", side_effect=[0x0027, 0]):
            self.assertEqual(
                self.pci_lib.get_lmt_cap_info(),
                pci_lib.CapabilityInfo(err_msg=None, id=0x27, version=0, offset=0x100, offset_next=0),
            )
