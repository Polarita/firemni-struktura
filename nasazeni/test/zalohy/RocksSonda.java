import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import org.rocksdb.*;

public class RocksSonda {
    public static void main(String[] args) throws RocksDBException {
        boolean queue = args.length == 3 && args[0].equals("fronta");
        if (!queue && !(args.length == 2 && args[0].equals("kontrola"))) {
            throw new IllegalArgumentException("kontrola databaze | fronta databaze sekundarni-adresar");
        }
        RocksDB.loadLibrary();
        try (Options options = new Options();
             DBOptions dbOptions = new DBOptions().setCreateIfMissing(false).setMaxOpenFiles(-1);
             ColumnFamilyOptions cfOptions = new ColumnFamilyOptions()) {
            List<byte[]> names = RocksDB.listColumnFamilies(options, args[1]);
            List<ColumnFamilyDescriptor> descriptors = new ArrayList<>();
            List<ColumnFamilyHandle> handles = new ArrayList<>();
            for (byte[] name : names) {
                descriptors.add(new ColumnFamilyDescriptor(name, cfOptions));
            }
            try (RocksDB db = queue
                    ? RocksDB.openAsSecondary(dbOptions, args[1], args[2], descriptors, handles)
                    : RocksDB.openReadOnly(dbOptions, args[1], descriptors, handles)) {
                try {
                    if (queue) {
                        System.out.println(countQueue(db, handles));
                    } else {
                        db.verifyChecksum();
                    }
                } finally {
                    for (ColumnFamilyHandle handle : handles) {
                        handle.close();
                    }
                }
            }
        }
    }

    private static long countQueue(RocksDB db, List<ColumnFamilyHandle> handles) throws RocksDBException {
        for (ColumnFamilyHandle handle : handles) {
            if (Arrays.equals(handle.getName(), "e".getBytes(StandardCharsets.US_ASCII))) {
                long count = 0;
                try (RocksIterator iterator = db.newIterator(handle)) {
                    for (iterator.seekToFirst(); iterator.isValid(); iterator.next()) {
                        if (iterator.key().length != Long.BYTES) {
                            throw new IllegalStateException("Neplatny klic fronty MX");
                        }
                        count++;
                    }
                    iterator.status();
                }
                return count;
            }
        }
        throw new IllegalStateException("Chybi rodina klicu e");
    }
}
