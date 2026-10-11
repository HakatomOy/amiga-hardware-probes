import struct
import unittest

import build
import results


def capture():
    image = bytearray(results.ADF_BYTES)
    raw = bytearray(results.SIZE)
    raw[:8] = b'A5IRQ001'
    struct.pack_into('>4H4I',raw,8,1,512,64,0,results.COUNT,results.SIZE,512,0)
    struct.pack_into('>H',raw,74,1)
    for index in range(results.COUNT):
        pos = 512+index*64
        source = index//192
        struct.pack_into('>4B',raw,pos,source,(index//32)%6,(index//2)%16,index%2)
        struct.pack_into('>H',raw,pos+6,2 if source==3 else 1)
        struct.pack_into('>B',raw,pos+26,2 if source in (0,3) else 6 if source==1 else 1)
        if source==3:
            struct.pack_into('>B',raw,pos+46,6)
    checksum = (-sum(struct.unpack('>16384I',raw))) & 0xffffffff
    struct.pack_into('>I',raw,28,checksum)
    image[results.OFFSET:results.OFFSET+results.SIZE] = raw
    return image


def repair_checksum(image):
    raw = bytearray(image[results.OFFSET:results.OFFSET+results.SIZE])
    struct.pack_into('>I',raw,28,0)
    struct.pack_into('>I',raw,28,(-sum(struct.unpack('>16384I',raw)))&0xffffffff)
    image[results.OFFSET:results.OFFSET+results.SIZE] = raw
    return image


class DiskTests(unittest.TestCase):
    def test_boot_checksum_and_reserved_region(self):
        boot = b'DOS\0'+b'\0'*4+struct.pack('>I',880)+bytes(range(256))*3
        image = build.make_image(boot,b'program')
        total = 0
        for word in struct.unpack('>256I',image[:1024]):
            total += word
            total = (total&0xffffffff)+(total>>32)
        self.assertEqual(total,0xffffffff)
        self.assertEqual(len(image),901120)
        self.assertEqual(image[1024:1031],b'program')
        self.assertEqual(image[results.OFFSET:],bytes(901120-results.OFFSET))

    def test_oversized_program_rejected(self):
        with self.assertRaises(ValueError):
            build.make_image(bytes(1025),b'')
        with self.assertRaises(ValueError):
            build.make_image(b'',bytes(build.PROGRAM_BYTES+1))

    def test_complete_capture(self):
        meta, records = results.decode(capture())
        self.assertEqual(meta['timeouts'],0)
        self.assertEqual(len(records),768)
        self.assertEqual(records[-1]['event_count'],2)
        self.assertEqual(results.compare((meta,records),(meta,records))['differing_records'],0)

    def test_no_capture_and_truncated_image_rejected(self):
        for image in (bytes(901120),bytes(42)):
            with self.assertRaises(ValueError):
                results.decode(image)

    def test_damaged_capture_rejected(self):
        image = capture()
        image[results.OFFSET+2000] ^= 1
        with self.assertRaisesRegex(ValueError,'checksum'):
            results.decode(image)

    def test_different_build_rejected(self):
        meta, records = results.decode(capture())
        other = dict(meta,source_id='different')
        with self.assertRaisesRegex(ValueError,'source IDs'):
            results.compare((meta,records),(other,records))

    def test_incomplete_capture_rejected_even_with_valid_checksum(self):
        image = capture()
        struct.pack_into('>I',image,results.OFFSET+16,767)
        with self.assertRaisesRegex(ValueError,'Incomplete'):
            results.decode(repair_checksum(image))

    def test_test_identity_damage_rejected_even_with_valid_checksum(self):
        image = capture()
        image[results.OFFSET+512] = 3
        with self.assertRaisesRegex(ValueError,'identity'):
            results.decode(repair_checksum(image))

    def test_timeout_is_preserved_as_an_observation(self):
        image = capture()
        struct.pack_into('>2H',image,results.OFFSET+512+4,1,0)
        meta, records = results.decode(repair_checksum(image))
        self.assertEqual(meta['timeouts'],1)
        self.assertEqual(records[0]['status'],'timeout')
        self.assertNotIn('event1_pc_offset',records[0])


if __name__ == '__main__':
    unittest.main()
