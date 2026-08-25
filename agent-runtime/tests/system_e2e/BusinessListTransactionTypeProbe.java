import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.PreparedStatement;
import java.sql.ResultSet;

/** Resolves one existing Transaction type without printing any database credentials. */
public final class BusinessListTransactionTypeProbe {

    private BusinessListTransactionTypeProbe() {
    }

    public static void main(String[] arguments) throws Exception {
        String url = System.getenv("BUSINESS_LIST_DB_URL");
        String username = System.getenv("BUSINESS_LIST_DB_USERNAME");
        String password = System.getenv("BUSINESS_LIST_DB_PASSWORD");
        if (url == null || username == null || password == null) {
            throw new IllegalStateException("business_list_live.database_configuration_missing");
        }

        String query = "SELECT TRANS_TYPE FROM t_transaction "
                + "WHERE TRANS_TYPE IS NOT NULL "
                + "AND CHAR_LENGTH(TRIM(TRANS_TYPE)) BETWEEN 1 AND 64 "
                + "ORDER BY TRANS_ID LIMIT 1";
        try (Connection connection = DriverManager.getConnection(url, username, password);
             PreparedStatement statement = connection.prepareStatement(query);
             ResultSet result = statement.executeQuery()) {
            if (!result.next()) {
                throw new IllegalStateException("business_list_live.transaction_type_missing");
            }
            String transactionType = result.getString(1);
            if (transactionType == null || transactionType.isBlank()
                    || transactionType.length() > 64
                    || transactionType.chars().anyMatch(Character::isISOControl)) {
                throw new IllegalStateException("business_list_live.transaction_type_invalid");
            }
            System.out.print(transactionType);
        }
    }
}
